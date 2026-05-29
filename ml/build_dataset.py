import re
from pathlib import Path

import nfl_data_py as nfl
import pandas as pd

DATA_DIR = Path(__file__).parent.parent / "Pass Blocking PFF"
ML_DIR = Path(__file__).parent

PFF_COLS = [
    "player", "position", "team_name", "player_game_count",
    "grades_pass_block", "hits_allowed", "hurries_allowed",
    "pressures_allowed", "sacks_allowed", "snap_counts_pass_block",
    "true_pass_set_grades_pass_block", "true_pass_set_hits_allowed",
    "true_pass_set_hurries_allowed", "true_pass_set_pressures_allowed",
    "true_pass_set_sacks_allowed", "true_pass_set_snap_counts_pass_block",
    "all_pass_pbwr", "true_pass_set_pbwr",
]

# PFF abbrev → nflverse abbrev
# nflverse normalizes all historical names to current abbreviations (always LA/LAC/LV)
TEAM_MAP = {
    "ARZ": "ARI",
    "BLT": "BAL",
    "CLV": "CLE",
    "HST": "HOU",
    "SL":  "LA",   # St. Louis Rams → LA Rams
    "SD":  "LAC",  # San Diego Chargers → LAC
    "OAK": "LV",   # Oakland Raiders → LV Raiders
}

TARGET_COLS = [
    "pass_epa_per_play", "pass_success_rate", "sack_rate", "qb_hit_rate",
    "team_pressure_rate", "wl_delta",
]


# ── Step 1 ────────────────────────────────────────────────────────────────────

def load_pff_players() -> pd.DataFrame:
    print("Step 1: Loading PFF filtered CSVs...")
    frames = []
    for path in sorted(DATA_DIR.glob("O-Line Data * Filtered.csv")):
        match = re.search(r"(\d{4})", path.name)
        if not match:
            continue
        year = int(match.group(1))
        df = pd.read_csv(path, usecols=PFF_COLS)
        df["year"] = year
        frames.append(df)
    players = pd.concat(frames, ignore_index=True)
    print(f"  {len(players)} player-season rows across {players['year'].nunique()} years")
    players.to_csv(ML_DIR / "raw_pff_players.csv", index=False)
    print("  Saved ml/raw_pff_players.csv")
    return players


# ── Step 2 ────────────────────────────────────────────────────────────────────

def load_nflverse() -> pd.DataFrame:
    print("Step 2: Loading nflverse play-by-play (2013-2025)...")
    years = list(range(2013, 2026))
    pbp = nfl.import_pbp_data(
        years,
        columns=["season", "season_type", "posteam", "epa", "success", "sack", "qb_hit", "cpoe", "qb_dropback"],
        include_participation=False,
    )
    pbp = pbp[(pbp["season_type"] == "REG") & (pbp["qb_dropback"] == 1)].copy()
    print(f"  {len(pbp)} dropback plays after filtering")

    agg = (
        pbp.groupby(["season", "posteam"])
        .agg(
            n_dropbacks=("epa", "count"),
            total_epa=("epa", "sum"),
            total_success=("success", "sum"),
            total_sacks=("sack", "sum"),
            total_qb_hits=("qb_hit", "sum"),
            avg_cpoe=("cpoe", "mean"),
        )
        .reset_index()
        .rename(columns={"season": "year", "posteam": "nflverse_team"})
    )
    print(f"  Aggregated to {len(agg)} team-seasons")
    agg.to_csv(ML_DIR / "raw_nflverse_team_season.csv", index=False)
    print("  Saved ml/raw_nflverse_team_season.csv")
    return agg


# ── Step 3 ────────────────────────────────────────────────────────────────────

def normalize_pff_team(team: str, year: int) -> str:
    return TEAM_MAP.get(team, team)


def join_data(players: pd.DataFrame, nflverse: pd.DataFrame) -> pd.DataFrame:
    print("Step 3: Joining PFF and nflverse data...")
    players = players.copy()
    players["nflverse_team"] = players.apply(
        lambda r: normalize_pff_team(r["team_name"], r["year"]), axis=1
    )
    merged = players.merge(nflverse, on=["year", "nflverse_team"], how="left")
    unmatched = merged[merged["n_dropbacks"].isna()]
    if len(unmatched) > 0:
        print(f"  WARNING: {len(unmatched)} unmatched rows:")
        print(unmatched[["player", "team_name", "nflverse_team", "year"]].drop_duplicates().to_string())
    else:
        print("  All rows matched — zero unmatched")
    print(f"  Joined frame: {len(merged)} rows")
    return merged


# ── Step 4 ────────────────────────────────────────────────────────────────────

def compute_team_season_features(grp: pd.DataFrame) -> dict:
    snaps = grp["snap_counts_pass_block"]
    total_snaps = snaps.sum()
    total_pressures = grp["pressures_allowed"].sum()
    total_sacks = grp["sacks_allowed"].sum()

    # Snap-weighted avg PBWR
    team_avg_pbwr = (grp["all_pass_pbwr"] * snaps).sum() / total_snaps
    team_min_pbwr = grp["all_pass_pbwr"].min()
    team_max_pbwr = grp["all_pass_pbwr"].max()
    team_std_pbwr = grp["all_pass_pbwr"].std()

    # Weak link: player with lowest PBWR among starters (>=40% of max snaps)
    snap_threshold = snaps.max() * 0.40
    starters = grp[snaps >= snap_threshold]
    wl_pool = starters if len(starters) >= 5 else grp
    wl_row = wl_pool.loc[wl_pool["all_pass_pbwr"].idxmin()]

    # True pass set variants
    tps_snaps = grp["true_pass_set_snap_counts_pass_block"]
    tps_total_snaps = tps_snaps.sum()
    tps_total_pressures = grp["true_pass_set_pressures_allowed"].sum()
    tps_total_sacks = grp["true_pass_set_sacks_allowed"].sum()
    tps_avg_pbwr = (grp["true_pass_set_pbwr"] * tps_snaps).sum() / tps_total_snaps if tps_total_snaps > 0 else None
    tps_min_pbwr = grp["true_pass_set_pbwr"].min()
    tps_max_pbwr = grp["true_pass_set_pbwr"].max()
    tps_std_pbwr = grp["true_pass_set_pbwr"].std()

    tps_threshold = tps_snaps.max() * 0.40
    tps_starters = grp[tps_snaps >= tps_threshold]
    tps_wl_pool = tps_starters if len(tps_starters) >= 5 else grp
    tps_wl_row = tps_wl_pool.loc[tps_wl_pool["true_pass_set_pbwr"].idxmin()]

    # nflverse columns (same for all players in group — take first)
    nfl_row = grp.iloc[0]
    n_dropbacks = nfl_row["n_dropbacks"]

    return {
        # team/roster counts
        "n_qualified": len(grp),
        "n_starter_qualified": len(starters),
        # all-pass team metrics
        "total_snaps": total_snaps,
        "total_pressures": total_pressures,
        "team_pressure_rate": total_pressures / total_snaps if total_snaps > 0 else None,
        "team_sack_rate_pff": total_sacks / total_snaps if total_snaps > 0 else None,
        "team_avg_pbwr": team_avg_pbwr,
        "team_min_pbwr": team_min_pbwr,
        "team_max_pbwr": team_max_pbwr,
        "team_std_pbwr": team_std_pbwr,
        "team_range_pbwr": team_max_pbwr - team_min_pbwr,
        "team_avg_grade": grp["grades_pass_block"].mean(),
        "team_min_grade": grp["grades_pass_block"].min(),
        "team_std_grade": grp["grades_pass_block"].std(),
        # weak link (all-pass)
        "wl_player": wl_row["player"],
        "wl_position": wl_row["position"],
        "wl_pbwr": wl_row["all_pass_pbwr"],
        "wl_delta": team_avg_pbwr - wl_row["all_pass_pbwr"],
        "wl_snap_share": wl_row["snap_counts_pass_block"] / total_snaps,
        "wl_pressure_rate": wl_row["pressures_allowed"] / wl_row["snap_counts_pass_block"] if wl_row["snap_counts_pass_block"] > 0 else None,
        # true pass set team metrics
        "tps_total_snaps": tps_total_snaps,
        "tps_total_pressures": tps_total_pressures,
        "tps_team_pressure_rate": tps_total_pressures / tps_total_snaps if tps_total_snaps > 0 else None,
        "tps_team_sack_rate_pff": tps_total_sacks / tps_total_snaps if tps_total_snaps > 0 else None,
        "tps_avg_pbwr": tps_avg_pbwr,
        "tps_min_pbwr": tps_min_pbwr,
        "tps_max_pbwr": tps_max_pbwr,
        "tps_std_pbwr": tps_std_pbwr,
        "tps_range_pbwr": tps_max_pbwr - tps_min_pbwr,
        "tps_avg_grade": grp["true_pass_set_grades_pass_block"].mean(),
        "tps_min_grade": grp["true_pass_set_grades_pass_block"].min(),
        "tps_std_grade": grp["true_pass_set_grades_pass_block"].std(),
        # weak link (true pass set)
        "tps_wl_player": tps_wl_row["player"],
        "tps_wl_position": tps_wl_row["position"],
        "tps_wl_pbwr": tps_wl_row["true_pass_set_pbwr"],
        "tps_wl_delta": tps_avg_pbwr - tps_wl_row["true_pass_set_pbwr"] if tps_avg_pbwr is not None else None,
        "tps_wl_snap_share": tps_wl_row["true_pass_set_snap_counts_pass_block"] / tps_total_snaps if tps_total_snaps > 0 else None,
        "tps_wl_pressure_rate": tps_wl_row["true_pass_set_pressures_allowed"] / tps_wl_row["true_pass_set_snap_counts_pass_block"] if tps_wl_row["true_pass_set_snap_counts_pass_block"] > 0 else None,
        # nflverse targets
        "n_dropbacks": n_dropbacks,
        "total_epa": nfl_row["total_epa"],
        "total_success": nfl_row["total_success"],
        "total_sacks_nfl": nfl_row["total_sacks"],
        "total_qb_hits": nfl_row["total_qb_hits"],
        "avg_cpoe": nfl_row["avg_cpoe"],
        "pass_epa_per_play": nfl_row["total_epa"] / n_dropbacks if n_dropbacks > 0 else None,
        "pass_success_rate": nfl_row["total_success"] / n_dropbacks if n_dropbacks > 0 else None,
        "sack_rate": nfl_row["total_sacks"] / n_dropbacks if n_dropbacks > 0 else None,
        "qb_hit_rate": nfl_row["total_qb_hits"] / n_dropbacks if n_dropbacks > 0 else None,
    }


def compute_features(merged: pd.DataFrame) -> pd.DataFrame:
    print("Step 4: Computing derived features per team-season...")
    rows = []
    for (year, team, nflverse_team), grp in merged.groupby(["year", "team_name", "nflverse_team"]):
        row = compute_team_season_features(grp)
        row["year"] = year
        row["team_name"] = team
        row["nflverse_team"] = nflverse_team
        rows.append(row)
    df = pd.DataFrame(rows)
    # Move identifiers to front
    id_cols = ["year", "team_name", "nflverse_team"]
    df = df[id_cols + [c for c in df.columns if c not in id_cols]]
    df = df.sort_values(["year", "team_name"]).reset_index(drop=True)
    print(f"  Computed features for {len(df)} team-seasons")
    return df


# ── Step 5 ────────────────────────────────────────────────────────────────────

def validate_and_save(df: pd.DataFrame) -> None:
    print("Step 5: Validating and saving...")
    print(f"  Shape: {df.shape}")

    null_counts = df.isnull().sum()
    null_cols = null_counts[null_counts > 0]
    if len(null_cols) > 0:
        print("  Null counts per column:")
        print(null_cols.to_string())
    else:
        print("  No nulls found")

    print("  Sample (5 rows):")
    print(df[["year", "team_name", "team_avg_pbwr", "wl_delta", "wl_player", "pass_epa_per_play", "sack_rate"]].head().to_string())

    missing_targets = [c for c in TARGET_COLS if c in df.columns and df[c].isnull().any()]
    assert not missing_targets, f"Nulls found in target columns: {missing_targets}"

    out_path = ML_DIR / "ml_dataset.csv"
    df.to_csv(out_path, index=False)
    print(f"  Saved ml/ml_dataset.csv ({len(df)} rows, {len(df.columns)} columns)")


# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    pff = load_pff_players()
    nflverse = load_nflverse()
    merged = join_data(pff, nflverse)
    dataset = compute_features(merged)
    validate_and_save(dataset)
    print("Done.")
