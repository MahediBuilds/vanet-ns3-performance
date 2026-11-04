#!/usr/bin/env python3
"""Animate every test point of one sweep side by side, on one clock.

Each row is one traced ns-3 run (vanet-highway --trace) of the sweep: the whole
2 km road with its vehicles and the data hops on air. Next to each road a bar
shows, live, the metric the sweep's graph plots (PDR, delay or throughput), so
you can watch how the varied setting changes the result.

Usage: python3 animate_sweep.py SWEEP OUT.gif TRACE [TRACE ...]
                                [--start 9] [--end 60] [--step 0.25] [--fps 8]
                                [--snapshot T OUT.png]
SWEEP is density, speed, load or range. Rows are sorted by the varied value.
"""
import argparse

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib import animation
from matplotlib.collections import LineCollection

from animate_trace import (DATA, DELIVERED, GRID, INK, INK2, PAYLOAD_BITS, RERR, ROAD, RREQ, SENDER, SETTINGS,
                           SURFACE, SWEEPS, VEHICLE, load, run_metrics)

# sweep -> (metric shown in the bar, unit, "higher is better")
METRIC = {
    "density": ("PDR", "%", True),
    "speed": ("delay", "ms", False),
    "load": ("throughput", "kbit/s per flow", True),
    "range": ("PDR", "%", True),
}
ROW_LABEL = {"density": "{:g} vehicles", "speed": "{:g} m/s", "load": "{:g} kbit/s", "range": "{:g} m range"}
LANE = 1.0
ARC = 2.6


class Run:
    """One traced run, prepared for fast per-frame lookups."""

    def __init__(self, path):
        self.meta, self.flows, self.times, self.xy, ev = load(path)
        self.D = np.array(ev["D"]) if ev["D"] else np.zeros((0, 3))
        C = ev["C"]
        self.C_t = np.array([c[0] for c in C])
        self.rreq = np.array([c[2] == "RREQ" for c in C], dtype=bool)
        self.rerr = np.array([c[2] == "RERR" for c in C], dtype=bool)
        self.C_node = np.array([c[1] for c in C], dtype=int)
        self.S_t = np.sort(np.array(ev["S"]))
        R = np.array(ev["R"]) if ev["R"] else np.zeros((0, 3))
        order = np.argsort(R[:, 0]) if len(R) else []
        self.R = R[order] if len(R) else R
        self.R_cumdelay = np.cumsum(self.R[:, 2]) if len(R) else np.zeros(0)
        self.final = run_metrics(self.meta, self.flows, ev)
        self.starts = np.array([f["start"] for f in self.flows])
        self.senders = sorted({f["src"] for f in self.flows})
        self.receivers = sorted({f["dst"] for f in self.flows})

    def positions(self, t):
        i = min(np.searchsorted(self.times, t), len(self.times) - 1)
        return self.xy[i]

    def metric(self, sweep, t):
        """Value of the sweep's metric over the run so far, as the graph would compute it."""
        n_s = np.searchsorted(self.S_t, t, side="right")
        n_r = np.searchsorted(self.R[:, 0], t, side="right") if len(self.R) else 0
        name = METRIC[sweep][0]
        if name == "PDR":
            return 100 * n_r / n_s if n_s else np.nan
        if name == "delay":
            return self.R_cumdelay[n_r - 1] / n_r if n_r else np.nan
        active = np.clip(min(t, self.meta["appStop"]) - self.starts, 0, None).mean()
        return n_r * PAYLOAD_BITS / active / 1000 / len(self.flows) if active > 0 else np.nan


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("sweep", choices=SWEEPS)
    ap.add_argument("out")
    ap.add_argument("traces", nargs="+")
    ap.add_argument("--start", type=float, default=9.0)
    ap.add_argument("--end", type=float, default=60.0)
    ap.add_argument("--step", type=float, default=0.25, help="simulated seconds per frame")
    ap.add_argument("--fps", type=int, default=8)
    ap.add_argument("--snapshot", nargs=2, metavar=("T", "PNG"))
    args = ap.parse_args()

    name, graph, key, fmt = SWEEPS[args.sweep]
    mname, munit, higher_better = METRIC[args.sweep]
    runs = sorted((Run(p) for p in args.traces), key=lambda r: r.meta[key])
    L = runs[0].meta["highwayLength"]
    lane_w = runs[0].meta["laneWidth"]
    n = len(runs)
    row_h = 4 * LANE + ARC + 1.2
    mi = {"PDR": 0, "delay": 1, "throughput": 2}[mname]
    finals = [r.final[mi] for r in runs]
    if args.sweep == "load":
        # the offered load is the natural top of the throughput scale
        mmax = max(r.meta["dataRateKbps"] for r in runs) * 1.05
    else:
        mmax = max(100 if mname == "PDR" else 0, np.nanmax(finals) * 1.6)

    fig = plt.figure(figsize=(12, 1.25 * n + 1.9), dpi=100, facecolor=SURFACE)
    top = 1 - 1.15 / fig.get_figheight()
    gs = fig.add_gridspec(1, 2, width_ratios=[4.0, 1.3], wspace=0.04, left=0.1, right=0.975, top=top, bottom=0.05)
    ax = fig.add_subplot(gs[0])
    axb = fig.add_subplot(gs[1], sharey=ax)
    for a in (ax, axb):
        a.set_facecolor(SURFACE)
        a.axis("off")
    ax.set_xlim(0, L)
    ax.set_ylim(-(n - 1) * row_h - 1.0, 4 * LANE + ARC + 0.4)
    axb.set_xlim(0, mmax * 1.5)

    fixed = ", ".join(f.format(runs[0].meta[k]) for k, f in SETTINGS if k != key)
    fig.text(0.015, 1 - 0.32 / fig.get_figheight(), f"{name} · how it shapes the “{graph}” graph",
             fontsize=15, fontweight="bold", color=INK, va="center")
    fig.text(0.015, 1 - 0.62 / fig.get_figheight(),
             f"ns-3 · AODV over 802.11p · 2 km highway · fixed: {fixed} · 10 UDP flows · seed "
             f"{int(runs[0].meta['run'])} · one row per test point, all on the same clock",
             fontsize=9.5, color=INK2, va="center")
    clock = fig.text(0.985, 1 - 0.32 / fig.get_figheight(), "", fontsize=12, color=INK, va="center", ha="right",
                     family="monospace")
    better = "higher is better" if higher_better else "lower is better"
    offered = "\ngrey bar = offered load" if args.sweep == "load" else ""
    axb.set_title(f"{mname} so far ({munit})\n{better} · tick = whole run{offered}", fontsize=8.5, color=INK2,
                  loc="left")
    handles = [
        plt.Line2D([], [], marker="s", ls="", ms=5, color=VEHICLE, label="vehicle"),
        plt.Line2D([], [], marker="s", ls="", ms=5, color=SENDER, label="sender"),
        plt.Line2D([], [], color=DATA, lw=1.4, label="data hop on air"),
        plt.Line2D([], [], marker="o", ls="", color=RREQ, label="RREQ"),
        plt.Line2D([], [], marker="x", ls="", color=RERR, mew=2, label="RERR (route broke)"),
        plt.Line2D([], [], marker="o", ls="", mfc="none", mec=DELIVERED, mew=2, label="delivered"),
    ]
    fig.legend(handles=handles, loc="upper center", bbox_to_anchor=(0.5, 1 - 0.78 / fig.get_figheight()),
               ncol=6, frameon=False, fontsize=8.5, labelcolor=INK2, handletextpad=0.4, columnspacing=1.6)

    rows = []
    for i, r in enumerate(runs):
        y0 = -i * row_h
        ax.add_patch(plt.Rectangle((0, y0), L, 4 * LANE, color=ROAD, zorder=0))
        ax.plot([0, L], [y0 + 2 * LANE] * 2, color="#c9a227", lw=1, zorder=1)
        ax.text(-L * 0.012, y0 + 2 * LANE, ROW_LABEL[args.sweep].format(r.meta[key]), ha="right",
                va="center", fontsize=10.5, fontweight="bold", color=INK)
        if i == n - 1:
            for m in range(0, int(L) + 1, 500):
                ax.text(m, y0 - 0.35, f"{m} m", ha="center", va="top", fontsize=7.5, color=INK2)
        # range scale bar so the varied range is visible in the range sweep
        ax.plot([L - r.meta["range"], L], [y0 + 4 * LANE + ARC + 0.1] * 2, color=GRID, lw=2)
        ax.text(L - r.meta["range"] - 12, y0 + 4 * LANE + ARC + 0.1, f"range {r.meta['range']:g} m", ha="right",
                va="center", fontsize=7, color=INK2)
        hops = LineCollection([], colors=DATA, linewidths=1.1, alpha=0.85, zorder=2)
        ax.add_collection(hops)
        rq = ax.scatter([], [], s=55, c=RREQ, alpha=0.45, linewidths=0, zorder=3)
        veh = ax.scatter([], [], s=9, marker="s", c=VEHICLE, linewidths=0, zorder=4)
        snd = ax.scatter([], [], s=16, marker="s", c=SENDER, linewidths=0, zorder=5)
        er = ax.scatter([], [], s=32, marker="x", c=RERR, linewidths=1.6, zorder=6)
        dl = ax.scatter([], [], s=90, marker="o", facecolors="none", edgecolors=DELIVERED, linewidths=1.6, zorder=6)
        # bar for the metric
        yb = y0 + 2 * LANE
        # in the load sweep the grey bar is the offered load of that row
        axb.barh(yb, r.meta["dataRateKbps"] if args.sweep == "load" else mmax, height=2.2, color=ROAD, zorder=0)
        bar = axb.barh(yb, 0, height=2.2, color=DATA if mname != "delay" else SENDER, zorder=1)[0]
        axb.plot([r.final[mi]] * 2 if np.isfinite(r.final[mi]) else [np.nan] * 2, [yb - 1.5, yb + 1.5],
                 color=INK, lw=1.6, zorder=2)
        val = axb.text(mmax * 1.03, yb, "", va="center", fontsize=9.5, color=INK, family="monospace")
        rows.append((r, y0, hops, rq, veh, snd, er, dl, bar, val))

    def lanes_y(xy, y0):
        lane = np.round(xy[:, 1] / lane_w)
        return y0 + (3 - lane) * LANE + LANE / 2

    def frame(t):
        lo = t - args.step
        for r, y0, hops, rq, veh, snd, er, dl, bar, val in rows:
            p = r.positions(t)
            x, y = p[:, 0].clip(0, L), lanes_y(p, y0)
            veh.set_offsets(np.c_[x, y])
            snd.set_offsets(np.c_[x[r.senders], y[r.senders]])
            segs = []
            if len(r.D):
                m = (r.D[:, 0] > lo) & (r.D[:, 0] <= t) & (r.D[:, 2] >= 0)
                base = y0 + 4 * LANE
                s = np.linspace(0, 1, 12)[:, None]
                for a, b in {(int(a), int(b)) for a, b in r.D[m][:, 1:3]}:
                    h = min(ARC, 0.3 + abs(x[b] - x[a]) / 110)
                    cx = (x[a] + x[b]) / 2
                    xs = (1 - s) ** 2 * x[a] + 2 * (1 - s) * s * cx + s ** 2 * x[b]
                    ys = base + 2 * (1 - s) * s * 2 * h
                    segs.append(np.c_[xs, ys])
            hops.set_segments(segs)
            cm = (r.C_t > lo) & (r.C_t <= t)
            q, e = r.C_node[cm & r.rreq], r.C_node[cm & r.rerr]
            rq.set_offsets(np.c_[x[q], y[q]] if len(q) else np.zeros((0, 2)))
            er.set_offsets(np.c_[x[e], y[e] + 0.7] if len(e) else np.zeros((0, 2)))
            if len(r.R):
                rm = (r.R[:, 0] > lo) & (r.R[:, 0] <= t)
                g = np.unique(r.R[rm][:, 1].astype(int))
            else:
                g = []
            dl.set_offsets(np.c_[x[g], y[g]] if len(g) else np.zeros((0, 2)))
            v = r.metric(args.sweep, t)
            bar.set_width(0 if not np.isfinite(v) else min(v, mmax))
            val.set_text("  –" if not np.isfinite(v) else f"{v:.1f} {munit.split()[0]}")
        clock.set_text(f"t = {t:5.1f} s")
        return []

    if args.snapshot:
        frame(float(args.snapshot[0]))
        fig.savefig(args.snapshot[1], dpi=130, facecolor=SURFACE)
        print(f"Wrote {args.snapshot[1]}")

    ts = np.arange(args.start, args.end + 1e-9, args.step)
    anim = animation.FuncAnimation(fig, frame, frames=ts, blit=False)
    writer = animation.FFMpegWriter(fps=args.fps, bitrate=2400) if args.out.endswith(".mp4") \
        else animation.PillowWriter(fps=args.fps)
    anim.save(args.out, writer=writer, savefig_kwargs={"facecolor": SURFACE})
    print(f"Wrote {args.out} ({len(ts)} frames, {args.step:g} s of simulation per frame)")


if __name__ == "__main__":
    main()
