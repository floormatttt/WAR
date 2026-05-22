# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Goal

Build **Offensive Line WAR (Wins Above Replacement)** for NFL players using PFF pass blocking data, play-by-play EPA data, and (eventually) All-22 tracking. The core metric is PBWR (Pass Block Win Rate); the long-term pipeline converts that into win value above a replacement-level player.

## Commands

### Frontend (React + Vite)
```
cd frontend
npm run dev       # start dev server
npm run build     # production build
npm run lint      # ESLint
npm run preview   # preview production build
```

### PFF Data Processing (Python)
```
python ".claude/skills/process-pff-oline-pass/process_oline.py" "<path_to_csv>" "<year>"
```
Or use the `/process-pff-oline-pass` skill — it handles file discovery and argument parsing automatically.

## Architecture

### Data Layer (`Pass Blocking PFF/`)
Processed CSVs live here, named `O-Line Data [year].csv` and `O-Line Data [year] Filtered.csv` (2013–2025). Source CSVs from PFF are named `offense_pass_blocking.csv` and dropped here before processing. Never read output files as input — always source from the raw `offense_pass_blocking*.csv`.

**Key columns in processed files:**
- `all_pass_pbwr` — PBWR across all pass block snaps: `(1 - pressures_allowed / snap_counts_pass_block) * 100`
- `true_pass_set_pbwr` — same formula but restricted to true pass sets (excludes screens, RPOs, etc.)
- Filtered files: players with `snap_counts_pass_block >= 20% of season max`, sorted by `all_pass_pbwr` descending

### Skills (`.claude/skills/`)
- **`process-pff-oline-pass/`** — invocable as `/process-pff-oline-pass [year]`. Runs `process_oline.py` on the raw PFF CSV and writes both output files. See `SKILL.md` for exact behavior.

### Frontend (`frontend/`)
React 19 + Vite app. Currently a placeholder — will eventually visualize WAR outputs. No routing or state management added yet.

## WAR Pipeline (in progress)

The intended calculation chain:
1. **PBWR** (have) → per-player pass blocking performance
2. **Replacement level** (not built) → weighted-avg PBWR of bottom tier of snap-qualified players, computed per season from the filtered CSVs
3. **EPA per pressure** (not built) → requires nflfastR / nfl_data_py play-by-play; `mean(EPA | pressure) - mean(EPA | clean pocket)`
4. **Pass blocking WAR** = `(replacement_pbwr - player_pbwr) / 100 * snaps * EPA_per_pressure / EPA_per_win`
   - EPA per win ≈ 13.5 (standard football analytics constant)
5. **Run blocking WAR** (not built) — needs PFF run blocking CSV with same structure
6. **Tracking-based credit attribution** (future) — SAM 3 on All-22 film to handle double teams, line games, stunts

## Roadmap Tasks (`.claude/CLAUDE.md`)
- Process PFF CSVs → `/process-pff-oline-pass` skill (done)
- SAM 3 tracking on All-22 film for OL/DL matchups
- ML model: individual tracking + raw data → EPA / success rate
- ML model: team-level EPA → determine unit vs. individual impact
- Generate final WAR values
