#!/usr/bin/env python3
"""Merge the per-run CSVs written by run_experiments.sh and draw the four
result graphs (mean with standard-deviation error bars).

Usage: python3 plot_results.py [results_dir]

Writes into results_dir:
  all_runs.csv   every run in one file
  summary.csv    mean and standard deviation of each metric per test point
  plots/*.png    the four graphs
"""
import csv
import glob
import os
import sys
from collections import defaultdict

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

METRICS = ["pdr", "delayMs", "throughputKbps", "lossRate"]

# experiment -> (column that the sweep varies, x-axis label)
SWEEPS = {
    "density": ("nVehicles", "Number of vehicles"),
    "speed": ("speed", "Mean vehicle speed (m/s)"),
    "load": ("dataRateKbps", "Offered load per flow (kbit/s)"),
    "range": ("range", "Communication range (m)"),
}

# (experiment, metric, y-axis label, file name)
GRAPHS = [
    ("density", "pdr", "Packet delivery ratio (%)", "density_vs_pdr.png"),
    ("speed", "delayMs", "Average end-to-end delay (ms)", "speed_vs_delay.png"),
    ("load", "throughputKbps", "Delivered throughput per flow (kbit/s)", "load_vs_throughput.png"),
    ("range", "pdr", "Packet delivery ratio (%)", "range_vs_pdr.png"),
]


def load_rows(results_dir):
    rows = []
    for path in sorted(glob.glob(os.path.join(results_dir, "raw", "*.csv"))):
        with open(path, newline="") as f:
            rows.extend(csv.DictReader(f))
    return rows


def summarise(rows):
    """Return {(experiment, x): {metric: (mean, std, runs)}}."""
    groups = defaultdict(lambda: defaultdict(list))
    for row in rows:
        x = float(row[SWEEPS[row["experiment"]][0]])
        for m in METRICS:
            groups[(row["experiment"], x)][m].append(float(row[m]))

    summary = {}
    for key, metrics in groups.items():
        summary[key] = {}
        for m, values in metrics.items():
            v = np.array(values)
            v = v[~np.isnan(v)]
            mean = v.mean() if len(v) else float("nan")
            std = v.std(ddof=1) if len(v) > 1 else 0.0
            summary[key][m] = (mean, std, len(v))
    return summary


def write_csvs(rows, summary, results_dir):
    with open(os.path.join(results_dir, "all_runs.csv"), "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

    with open(os.path.join(results_dir, "summary.csv"), "w", newline="") as f:
        writer = csv.writer(f)
        header = ["experiment", "x"]
        for m in METRICS:
            header += [f"{m}_mean", f"{m}_std"]
        writer.writerow(header + ["runs"])
        for (exp, x) in sorted(summary):
            stats = summary[(exp, x)]
            line = [exp, x]
            for m in METRICS:
                line += [round(stats[m][0], 3), round(stats[m][1], 3)]
            writer.writerow(line + [stats["pdr"][2]])


def plot(summary, plots_dir):
    for exp, metric, ylabel, fname in GRAPHS:
        xs = sorted(x for (e, x) in summary if e == exp)
        if not xs:
            print(f"No data for '{exp}', skipping {fname}")
            continue
        means = [summary[(exp, x)][metric][0] for x in xs]
        stds = [summary[(exp, x)][metric][1] for x in xs]

        fig, ax = plt.subplots(figsize=(6, 4))
        ax.errorbar(xs, means, yerr=stds, marker="o", capsize=4, label="AODV")
        if exp == "load":
            ax.plot(xs, xs, "--", color="grey", label="offered = delivered")
        if metric == "pdr":
            ax.set_ylim(0, 105)
        ax.set_xlabel(SWEEPS[exp][1])
        ax.set_ylabel(ylabel)
        ax.set_xticks(xs)
        ax.grid(alpha=0.3)
        ax.legend()
        fig.tight_layout()
        fig.savefig(os.path.join(plots_dir, fname), dpi=200)
        plt.close(fig)
        print(f"Wrote {os.path.join(plots_dir, fname)}")


def main():
    results_dir = sys.argv[1] if len(sys.argv) > 1 else "results"
    rows = load_rows(results_dir)
    if not rows:
        sys.exit(f"No CSV files found in {os.path.join(results_dir, 'raw')}")
    summary = summarise(rows)
    write_csvs(rows, summary, results_dir)
    plots_dir = os.path.join(results_dir, "plots")
    os.makedirs(plots_dir, exist_ok=True)
    plot(summary, plots_dir)


if __name__ == "__main__":
    main()
