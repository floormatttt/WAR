# Plan: Weak Link Analysis for O-Line Pass Protection

## Context
We have 13 seasons (2013–2025) of filtered per-player PBWR data in `Pass Blocking PFF/O-Line Data [year] Filtered.csv`. The goal is to quantify how detrimental the weakest blocker on each team is — both as a raw performance gap and as a projected pressure cost when a defense intelligently targets that player.

---

## Approach

Single self-contained Python script: `weak_link_analysis.py` at project root.

**Output:** `Pass Blocking PFF/Weak Link Analysis.csv` — one row per team-season (~416 rows).

---

## Key Formulas

### Per-player (derived columns)
```
pressure_rate = pressures_allowed / snap_counts_pass_block
tps_pressure_rate = true_pass_set_pressures_allowed / true_pass_set_snap_counts_pass_block
```

### Team-level (per `year` + `team_name` group)
```
naive_team_pressure_rate = total_pressures / total_snaps          # snap-weighted avg
snap_weighted_pbwr       = sum(pbwr_i * snaps_i) / total_snaps
min_pbwr                 = min(all_pass_pbwr) across team roster
wl_delta_pbwr            = snap_weighted_pbwr - min_pbwr           # the "gap"
```

### Concentration targeting model (alpha = 0.40)
The weakest blocker's effective targeting share is set to `alpha = 0.40` (vs. their natural ~1/n share). All other players' shares are renormalized to sum to `1 - alpha`.
```
adjusted_share_worst = alpha
adjusted_share_i     = (snaps_i / sum_snaps_excl_worst) * (1 - alpha)   for i != worst

conc_team_pressure_rate = sum(pressure_rate_i * adjusted_share_i)
conc_delta_pressures    = (conc_team_pressure_rate - naive_team_pressure_rate) * total_snaps
```
Alpha = 0.40 means the defense directs 40% of its pass rush at the weakest blocker, a ~2.4x overload for a 6-man unit. Alpha is a named constant so it can be adjusted.

### Full-targeting upper bound
```
full_targeting_pressure_rate = weak_link_pressure_rate   (all pressure to worst player)
full_delta_pressures         = (full - naive) * total_snaps
```

### Replacement value delta
"How many pressures does the weak link add vs. replacing them with the team's average?"
```
team_avg_pr_excl_worst      = snap-weighted pressure_rate of all players except worst
replaced_pressures          = total_pressures - wl_pressures + team_avg_pr_excl_worst * wl_snaps
replacement_delta_pressures = (naive_pr - replaced_pr) * total_snaps
```

All metrics are computed in parallel for **true pass set** (prefixed `tps_`), which excludes screens/RPOs and is the purer signal.

---

## Implementation

### Functions

| Function | Responsibility |
|---|---|
| `load_all_filtered_csvs(data_dir)` | Glob all `O-Line Data * Filtered.csv`, extract year from filename, concatenate, derive pressure rate columns |
| `compute_team_season(grp, alpha)` | All metrics for one `(year, team_name)` group → flat dict |
| `run_analysis(alpha)` | `groupby(['year','team_name'])`, call above, assemble + sort DataFrame |
| `print_summary(df)` | Printed report: dataset overview, avg weak link cost, top 10 worst/best, position breakdown, year-over-year trend |
| `main()` | `run_analysis()` → save CSV → `print_summary()` |

### Output CSV columns
```
year, team_name,
n_qualified, total_snaps, total_pressures,
naive_team_pressure_rate, naive_team_pbwr, snap_weighted_pbwr,
min_pbwr, weak_link_player, weak_link_position, weak_link_snaps,
weak_link_pressure_rate, wl_delta_pbwr,
conc_team_pressure_rate, conc_delta_pressures,
full_targeting_pressure_rate, full_delta_pressures,
replacement_delta_pressures,
tps_naive_team_pressure_rate, tps_naive_team_pbwr, tps_snap_weighted_pbwr,
tps_min_pbwr, tps_weak_link_player, tps_weak_link_position,
tps_weak_link_pressure_rate, tps_wl_delta_pbwr,
tps_conc_delta_pressures, tps_full_delta_pressures,
tps_replacement_delta_pressures
```

### No new dependencies
`pandas`, `pathlib`, `glob`, `re` only — same stack as `process_oline.py`.

---

## Files

| File | Action |
|---|---|
| `weak_link_analysis.py` | **Create** (new script at project root) |
| `Pass Blocking PFF/Weak Link Analysis.csv` | **Generated output** |
| `Pass Blocking PFF/O-Line Data * Filtered.csv` | Read-only inputs |
| `.claude/skills/process-pff-oline-pass/process_oline.py` | Style reference |

---

## Verification
1. Run `python weak_link_analysis.py` — should exit cleanly and print summary
2. Check output CSV has ~416 rows (32 teams × 13 years, minus any team-seasons with <2 qualified players)
3. Spot-check: 2024 KC should show Creed Humphrey as a top performer, not the weak link
4. `conc_delta_pressures` should be positive for every row (targeting always costs more than naive)
5. `wl_delta_pbwr` should be > 0 for every row (weak link is always below team average)
