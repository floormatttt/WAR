---
name: process-pff-oline-pass
description: Process a raw PFF O-Line pass blocking CSV. Calculates Pass Block Win Rate (PBWR) for all pass sets and true pass sets, produces a full CSV and a snap-filtered CSV sorted by PBWR, and names both files with the provided year. Use when the user has a PFF offense_pass_blocking CSV and wants to generate O-Line Data files.
user-invocable: true
allowed-tools:
  - Read
  - Write
  - Bash
  - Glob
---

# /process-pff-oline-pass — PFF O-Line CSV Processor

Arguments passed: `$ARGUMENTS`

Find the source CSV by globbing `Pass Blocking PFF/offense_pass_blocking*.csv`. All data comes exclusively from this file — do not source from any other CSV. If multiple matches are found, list them and ask the user which to use.

Output files are written to the same `Pass Blocking PFF/` directory:
- **`O-Line Data [year].csv`** — full dataset with PBWR columns added
- **`O-Line Data [year] Filtered.csv`** — players with snaps ≥ 20% of the top snap player, sorted by all-pass-sets PBWR descending

---

## Arguments

`$ARGUMENTS` must contain a 4-digit year. If not present, ask: "What year is this dataset?"

---

## Steps

### 1. Parse the year

Extract the 4-digit year from `$ARGUMENTS`. If missing, ask before proceeding.

### 2. Locate the source CSV

Glob `Pass Blocking PFF/offense_pass_blocking*.csv`. If one match, use it. If multiple, list and ask. If none, tell the user no source CSV was found.

### 3. Run the processing script

```
python ".claude/skills/process-pff-oline-pass/process_oline.py" "<matched_csv_path>" "<year>"
```

The script will:
- Read exclusively from the matched `offense_pass_blocking*.csv`
- Calculate **all-pass PBWR** = `(1 - pressures_allowed / snap_counts_pass_block) * 100`
- Calculate **true-pass-set PBWR** = `(1 - true_pass_set_pressures_allowed / true_pass_set_snap_counts_pass_block) * 100`
- Save `O-Line Data [year].csv` (full dataset + PBWR columns)
- Save `O-Line Data [year] Filtered.csv` (snaps ≥ 20% of max, sorted by all-pass PBWR descending)

### 4. Handle duplicate year files

If `O-Line Data [year].csv` or `O-Line Data [year] Filtered.csv` already exist for the same year, overwrite them silently. Do not delete output files for any other year.

### 5. Report results

Print:
- Path to both output files
- Number of players in the filtered CSV
- Snap threshold used (20% of max)
- Top 5 players by all-pass PBWR (player, position, team, snaps, all_pass_pbwr, true_pass_set_pbwr)
