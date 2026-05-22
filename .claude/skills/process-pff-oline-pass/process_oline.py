"""
Process PFF O-Line pass blocking CSV.

Usage:
    python process_oline.py <input_csv> <year>

Example:
    python process_oline.py offense_pass_blocking.csv 2024
"""

import sys
import os
import pandas as pd


def calculate_pbwr(pressures, snaps):
    """Pass Block Win Rate = (1 - pressures / snaps) * 100"""
    return ((1 - pressures / snaps) * 100).round(2)


def process(input_path: str, year: str):
    df = pd.read_csv(input_path)

    # Calculate PBWR for all pass sets and true pass sets
    df["all_pass_pbwr"] = calculate_pbwr(
        df["pressures_allowed"], df["snap_counts_pass_block"]
    )
    df["true_pass_set_pbwr"] = calculate_pbwr(
        df["true_pass_set_pressures_allowed"], df["true_pass_set_snap_counts_pass_block"]
    )

    out_dir = os.path.dirname(os.path.abspath(input_path))

    # Full CSV
    full_path = os.path.join(out_dir, f"O-Line Data {year}.csv")
    df.to_csv(full_path, index=False)
    print(f"Saved full CSV: {full_path}")

    # Filtered CSV: players with snaps >= 20% of the max snap player
    max_snaps = df["snap_counts_pass_block"].max()
    threshold = max_snaps * 0.20
    filtered = df[df["snap_counts_pass_block"] >= threshold].copy()
    filtered = filtered.sort_values("all_pass_pbwr", ascending=False)

    filtered_path = os.path.join(out_dir, f"O-Line Data {year} Filtered.csv")
    filtered.to_csv(filtered_path, index=False)
    print(
        f"Saved filtered CSV ({len(filtered)} players, snap threshold >= {threshold:.0f}): {filtered_path}"
    )


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python process_oline.py <input_csv> <year>")
        sys.exit(1)

    process(sys.argv[1], sys.argv[2])
