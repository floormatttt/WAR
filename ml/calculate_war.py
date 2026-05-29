import re
from pathlib import Path

import numpy as np
import pandas as pd

DATA_DIR = Path(__file__).parent.parent / "Pass Blocking PFF"

POS_MAP = {
    "LT": "T", "RT": "T", "T": "T",
    "LG": "G", "RG": "G", "G": "G",
    "C": "C",
}

# Learned linear model weights
W_PBWR_CONTRIB = 0.018201
W_PRESSURE_RATE = 0.006666
W_WEAK_LINK = 0.005681
EPA_PER_WIN = 13.5
REPLACEMENT_BOTTOM_PCT = 0.20
WEAK_LINK_MIN_SNAP_PCT = 0.40


def load_data() -> pd.DataFrame:
    print("Step 1 — Loading filtered CSVs...")
    frames = []
    for f in sorted(DATA_DIR.glob("O-Line Data * Filtered.csv")):
        m = re.search(r"(\d{4})", f.name)
        if not m:
            continue
        year = int(m.group(1))
        df = pd.read_csv(f)
        df["year"] = year
        frames.append(df)
    data = pd.concat(frames, ignore_index=True)
    print(f"  Loaded {len(data):,} player-seasons across {data['year'].nunique()} seasons.")

    required = ["player", "position", "team_name", "snap_counts_pass_block",
                "pressures_allowed", "all_pass_pbwr", "year"]
    missing = [c for c in required if c not in data.columns]
    if missing:
        raise ValueError(f"Missing columns: {missing}")

    data["position"] = data["position"].map(POS_MAP)
    data = data.dropna(subset=["position"])
    data["snap_counts_pass_block"] = pd.to_numeric(data["snap_counts_pass_block"], errors="coerce")
    data["pressures_allowed"] = pd.to_numeric(data["pressures_allowed"], errors="coerce")
    data["all_pass_pbwr"] = pd.to_numeric(data["all_pass_pbwr"], errors="coerce")
    data = data.dropna(subset=["snap_counts_pass_block", "pressures_allowed", "all_pass_pbwr"])

    print(f"  After cleaning: {len(data):,} rows, positions: {sorted(data['position'].unique())}")
    return data


def compute_replacement_levels(data: pd.DataFrame) -> pd.DataFrame:
    print("\nStep 2 — Computing replacement levels per position-season...")
    records = []
    for (year, pos), grp in data.groupby(["year", "position"]):
        grp_sorted = grp.sort_values("all_pass_pbwr")
        n_bottom = max(1, int(np.ceil(len(grp_sorted) * REPLACEMENT_BOTTOM_PCT)))
        bottom = grp_sorted.iloc[:n_bottom]
        total_snaps = bottom["snap_counts_pass_block"].sum()
        if total_snaps == 0:
            repl_pbwr = grp_sorted["all_pass_pbwr"].iloc[0]
            repl_pressure_rate = (grp_sorted["pressures_allowed"].iloc[0] /
                                  grp_sorted["snap_counts_pass_block"].iloc[0])
        else:
            repl_pbwr = (bottom["all_pass_pbwr"] * bottom["snap_counts_pass_block"]).sum() / total_snaps
            repl_pressure_rate = bottom["pressures_allowed"].sum() / total_snaps
        records.append({
            "year": year,
            "position": pos,
            "replacement_pbwr": repl_pbwr,
            "replacement_pressure_rate": repl_pressure_rate,
            "n_replacement_players": n_bottom,
        })
    repl_df = pd.DataFrame(records)

    print("\n  Replacement-level PBWR by position and season:")
    pivot = repl_df.pivot_table(index="year", columns="position", values="replacement_pbwr")
    print(pivot.round(2).to_string())
    print("\n  Replacement-level pressure rate by position and season:")
    pivot_pr = repl_df.pivot_table(index="year", columns="position", values="replacement_pressure_rate")
    print(pivot_pr.round(4).to_string())

    return repl_df


def identify_weak_links(data: pd.DataFrame) -> pd.Series:
    """Return boolean Series marking each player as their team's weak link for that season."""
    is_weak = pd.Series(False, index=data.index)
    for (year, team), grp in data.groupby(["year", "team_name"]):
        max_snaps = grp["snap_counts_pass_block"].max()
        threshold = WEAK_LINK_MIN_SNAP_PCT * max_snaps
        qualified = grp[grp["snap_counts_pass_block"] >= threshold]
        if qualified.empty:
            continue
        weak_idx = qualified["all_pass_pbwr"].idxmin()
        is_weak.loc[weak_idx] = True
    return is_weak


def compute_war(data: pd.DataFrame, repl_df: pd.DataFrame) -> pd.DataFrame:
    print("\nStep 3 — Calculating Player EPA contributions and WAR...")
    data = data.copy()

    data["pressure_rate"] = data["pressures_allowed"] / data["snap_counts_pass_block"]

    # Team-season total snaps (sum of all players on that team that season)
    team_snaps = (data.groupby(["year", "team_name"])["snap_counts_pass_block"]
                  .sum().rename("team_total_snaps").reset_index())
    data = data.merge(team_snaps, on=["year", "team_name"], how="left")

    # Team PBWR range for weak-link penalty
    team_pbwr_stats = (data.groupby(["year", "team_name"])["all_pass_pbwr"]
                       .agg(team_pbwr_max="max", team_pbwr_min="min").reset_index())
    team_pbwr_stats["team_pbwr_range"] = team_pbwr_stats["team_pbwr_max"] - team_pbwr_stats["team_pbwr_min"]
    data = data.merge(team_pbwr_stats[["year", "team_name", "team_pbwr_range"]], on=["year", "team_name"], how="left")

    data["is_weak_link"] = identify_weak_links(data)

    data = data.merge(repl_df, on=["year", "position"], how="left")

    pbwr_contrib = data["all_pass_pbwr"] * data["snap_counts_pass_block"] / data["team_total_snaps"]
    data["player_epa"] = (W_PBWR_CONTRIB * pbwr_contrib
                          - W_PRESSURE_RATE * data["pressure_rate"]
                          - data["is_weak_link"].astype(float) * W_WEAK_LINK * data["team_pbwr_range"])

    repl_pbwr_contrib = data["replacement_pbwr"] * data["snap_counts_pass_block"] / data["team_total_snaps"]
    data["replacement_epa"] = (W_PBWR_CONTRIB * repl_pbwr_contrib
                               - W_PRESSURE_RATE * data["replacement_pressure_rate"])

    data["epa_above_replacement"] = data["player_epa"] - data["replacement_epa"]
    data["pass_blocking_war"] = data["epa_above_replacement"] / EPA_PER_WIN

    print(f"  WAR computed for {len(data):,} player-seasons.")
    return data


def save_outputs(data: pd.DataFrame) -> None:
    print("\nStep 4 — Saving output files...")
    out_cols = [
        "player", "player_id", "position", "team_name", "year",
        "snap_counts_pass_block", "pressures_allowed", "all_pass_pbwr",
        "pressure_rate", "is_weak_link", "team_pbwr_range",
        "player_epa", "replacement_epa", "epa_above_replacement", "pass_blocking_war",
    ]
    out_cols = [c for c in out_cols if c in data.columns]

    for year, grp in data.groupby("year"):
        out_path = DATA_DIR / f"O-Line Data {year} WAR.csv"
        grp[out_cols].sort_values("pass_blocking_war", ascending=False).to_csv(out_path, index=False)
    print(f"  Saved {data['year'].nunique()} individual year WAR files.")

    career = (data.groupby(["player", "position"])
              .agg(
                  seasons=("year", "nunique"),
                  career_snaps=("snap_counts_pass_block", "sum"),
                  career_pressures=("pressures_allowed", "sum"),
                  career_war=("pass_blocking_war", "sum"),
              )
              .reset_index()
              .sort_values("career_war", ascending=False))
    career_path = DATA_DIR / "O-Line WAR Career.csv"
    career.to_csv(career_path, index=False)
    print(f"  Saved career leaderboard: {career_path}")

    print("\n--- Top 15 Individual Tackle-Seasons by WAR ---")
    t_seasons = (data[data["position"] == "T"]
                 .nlargest(15, "pass_blocking_war")
                 [["player", "team_name", "year", "snap_counts_pass_block", "all_pass_pbwr", "pass_blocking_war"]])
    print(t_seasons.to_string(index=False))

    print("\n--- Top 15 Individual Guard-Seasons by WAR ---")
    g_seasons = (data[data["position"] == "G"]
                 .nlargest(15, "pass_blocking_war")
                 [["player", "team_name", "year", "snap_counts_pass_block", "all_pass_pbwr", "pass_blocking_war"]])
    print(g_seasons.to_string(index=False))

    print("\n--- Top 15 Individual Center-Seasons by WAR ---")
    c_seasons = (data[data["position"] == "C"]
                 .nlargest(15, "pass_blocking_war")
                 [["player", "team_name", "year", "snap_counts_pass_block", "all_pass_pbwr", "pass_blocking_war"]])
    print(c_seasons.to_string(index=False))

    print("\n--- Top 15 Career WAR Leaders ---")
    print(career.head(15)[["player", "position", "seasons", "career_snaps", "career_war"]].to_string(index=False))


if __name__ == "__main__":
    data = load_data()
    repl_df = compute_replacement_levels(data)
    data = compute_war(data, repl_df)
    save_outputs(data)
    print("\nDone.")
