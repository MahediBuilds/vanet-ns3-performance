#!/usr/bin/env python3
"""Animate an ns-3 run recorded with vanet-highway --trace=FILE.

Everything drawn comes from the ns-3 trace: vehicle positions, each data frame
put on air (one arc per hop), AODV control frames and packets reaching their
receiver. Writes an animated GIF (or MP4 if the name ends in .mp4 and ffmpeg
is installed) and optionally a PNG snapshot.

Usage: python3 animate_trace.py TRACE OUT.gif [--start 9] [--end 60] [--step 0.25]
                                [--fps 8] [--snapshot T OUT.png]
"""
import argparse
import csv
from collections import defaultdict

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib import animation
from matplotlib.collections import LineCollection

# Reference palette from the dataviz skill (light mode). Colour is never the only
# cue: each event type also has its own marker shape and a legend entry.
SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK2 = "#52514e"
GRID = "#d9d8d3"
ROAD = "#e9e8e3"
VEHICLE = "#8c8b85"
DATA = "#2a78d6"  # data frame hop
SENDER = "#eb6834"  # flow source
DELIVERED = "#0ca30c"  # status good
RERR = "#d03b3b"  # status critical
RREQ = "#86b6ef"  # light blue: route discovery flood

ROWS = 2  # the 2 km road is drawn as two 1 km rows so vehicles stay visible
LANE_H = 1.0  # drawing units per lane
ARC_MAX = 3.2  # tallest hop arc, drawing units
ROW_H = 4 * LANE_H + ARC_MAX + 1.6


def load(path):
    meta, flows = {}, []
    pos = defaultdict(dict)  # time -> node -> (x, lane)
    events = defaultdict(list)
    with open(path) as f:
        first = f.readline()
        for kv in first[1:].split():
            k, v = kv.split("=")
            meta[k] = float(v)
        for row in csv.reader(f):
            kind = row[0]
            if kind == "P":
                pos[float(row[1])][int(row[2])] = (float(row[3]), float(row[4]))
            elif kind == "F":
                flows.append({"id": int(row[1]), "src": int(row[2]), "dst": int(row[3]),
                              "port": int(row[4]), "start": float(row[5])})
            elif kind == "D":
                events["D"].append((float(row[1]), int(row[2]), int(row[3])))
            elif kind == "C":
                events["C"].append((float(row[1]), int(row[2]), row[3]))
            elif kind == "S":
                events["S"].append(float(row[1]))
            elif kind == "R":
                events["R"].append((float(row[1]), int(row[2]), float(row[5])))
    times = np.array(sorted(pos))
    n = int(meta["nVehicles"])
    xy = np.array([[pos[t][i] for i in range(n)] for t in times])  # [time, node, (x, y)]
    return meta, flows, times, xy, events


def screen(xy, meta):
    """Road coordinates -> drawing coordinates (row layout, westbound lanes on top)."""
    seg = meta["highwayLength"] / ROWS
    x = np.clip(xy[..., 0], 0, meta["highwayLength"] - 1e-6)
    row = np.floor(x / seg)
    lane = np.round(xy[..., 1] / meta["laneWidth"])
    sx = x - row * seg
    sy = -row * ROW_H + (3 - lane) * LANE_H + LANE_H / 2
    return sx, sy, row


def arc(x0, y0, x1, y1, same_row, seg):
    """Points of a hop arc above the road (straight line if the hop crosses rows)."""
    s = np.linspace(0, 1, 16)
    if not same_row:
        return np.c_[x0 + (x1 - x0) * s, y0 + (y1 - y0) * s]
    base = np.floor(max(y0, y1) / ROW_H) * ROW_H + 4 * LANE_H  # top edge of this row's road
    h = min(ARC_MAX, 0.4 + abs(x1 - x0) / seg * 18)
    cx, cy = (x0 + x1) / 2, base + 2 * h
    u = 1 - s
    xs = u * u * x0 + 2 * u * s * cx + s * s * x1
    ys = u * u * base + 2 * u * s * cy + s * s * base
    return np.c_[xs, ys]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("trace")
    ap.add_argument("out")
    ap.add_argument("--start", type=float, default=9.0)
    ap.add_argument("--end", type=float, default=60.0)
    ap.add_argument("--step", type=float, default=0.25, help="simulated seconds per frame")
    ap.add_argument("--fps", type=int, default=8)
    ap.add_argument("--snapshot", nargs=2, metavar=("T", "PNG"))
    args = ap.parse_args()

    meta, flows, times, xy, ev = load(args.trace)
    L, rng, seg = meta["highwayLength"], meta["range"], meta["highwayLength"] / ROWS
    senders = {f["src"] for f in flows}
    receivers = {f["dst"] for f in flows}

    D = np.array(ev["D"]) if ev["D"] else np.zeros((0, 3))
    C = ev["C"]
    C_t = np.array([c[0] for c in C])
    S_t = np.sort(np.array(ev["S"]))
    R = np.array(ev["R"]) if ev["R"] else np.zeros((0, 3))
    R_t = np.sort(R[:, 0]) if len(R) else np.zeros(0)
    rerr_mask = np.array([c[2] == "RERR" for c in C], dtype=bool)

    fig = plt.figure(figsize=(12, 6.4), dpi=100, facecolor=SURFACE)
    gs = fig.add_gridspec(2, 1, height_ratios=[3.3, 1], hspace=0.28, left=0.05, right=0.985, top=0.9, bottom=0.08)
    ax = fig.add_subplot(gs[0])
    ax2 = fig.add_subplot(gs[1])
    for a in (ax, ax2):
        a.set_facecolor(SURFACE)

    # Road
    ax.set_xlim(-30, seg + 10)
    ax.set_ylim(-(ROWS - 1) * ROW_H - 1.4, 4 * LANE_H + ARC_MAX * 2 + 0.3)
    ax.axis("off")
    for r in range(ROWS):
        y0 = -r * ROW_H
        ax.add_patch(plt.Rectangle((0, y0), seg, 4 * LANE_H, color=ROAD, zorder=0))
        for k in (1, 3):
            ax.plot([0, seg], [y0 + k * LANE_H] * 2, color=GRID, lw=0.8, ls=(0, (4, 6)), zorder=1)
        ax.plot([0, seg], [y0 + 2 * LANE_H] * 2, color="#c9a227", lw=1.2, zorder=1)
        ax.text(-8, y0 + 3 * LANE_H, "◀ W", ha="right", va="center", fontsize=8, color=INK2)
        ax.text(-8, y0 + 1 * LANE_H, "E ▶", ha="right", va="center", fontsize=8, color=INK2)
        for m in np.arange(0, seg + 1, 250):
            ax.text(m, y0 - 0.55, f"{int(m + r * seg)} m", ha="center", va="top", fontsize=7.5, color=INK2)
    # Range scale bar
    yb = 4 * LANE_H + ARC_MAX * 2
    ax.plot([seg - rng, seg], [yb, yb], color=INK2, lw=2, solid_capstyle="butt")
    ax.text(seg - rng / 2, yb - 0.25, f"radio range {rng:.0f} m", ha="center", va="top", fontsize=8, color=INK2)

    hops = LineCollection([], colors=DATA, linewidths=1.4, alpha=0.85, zorder=2)
    ax.add_collection(hops)
    veh = ax.scatter([], [], s=26, marker="s", c=VEHICLE, edgecolors=SURFACE, linewidths=0.6, zorder=4)
    snd = ax.scatter([], [], s=46, marker="s", c=SENDER, edgecolors=SURFACE, linewidths=0.8, zorder=5)
    rcv = ax.scatter([], [], s=110, marker="o", facecolors="none", edgecolors=SENDER, linewidths=1.4, zorder=5)
    rreq = ax.scatter([], [], s=150, marker="o", c=RREQ, alpha=0.45, linewidths=0, zorder=3)
    dlv = ax.scatter([], [], s=230, marker="o", facecolors="none", edgecolors=DELIVERED, linewidths=2.2, zorder=6)
    rerr = ax.scatter([], [], s=70, marker="x", c=RERR, linewidths=2.2, zorder=6)

    title = fig.text(0.05, 0.955, "", fontsize=15, fontweight="bold", color=INK, va="center")
    sub = fig.text(0.05, 0.918, "", fontsize=9.5, color=INK2, va="center")
    stats = fig.text(0.985, 0.918, "", fontsize=9.5, color=INK, va="center", ha="right", family="monospace")

    handles = [
        plt.Line2D([], [], marker="s", ls="", color=VEHICLE, label="vehicle"),
        plt.Line2D([], [], marker="s", ls="", color=SENDER, label="flow sender"),
        plt.Line2D([], [], marker="o", ls="", mfc="none", mec=SENDER, label="flow receiver"),
        plt.Line2D([], [], color=DATA, lw=1.6, label="data frame on air (one arc per hop)"),
        plt.Line2D([], [], marker="o", ls="", color=RREQ, label="AODV RREQ broadcast"),
        plt.Line2D([], [], marker="x", ls="", color=RERR, mew=2, label="AODV RERR (route broke)"),
        plt.Line2D([], [], marker="o", ls="", mfc="none", mec=DELIVERED, mew=2, label="packet delivered"),
    ]
    ax.legend(handles=handles, loc="upper left", bbox_to_anchor=(0, 1.02), ncol=4, frameon=False, fontsize=8.5,
              labelcolor=INK2, handletextpad=0.4, columnspacing=1.4)

    # Lower panel: packets sent and delivered per second over the whole run
    bins = np.arange(0, meta["simTime"] + 1, 1.0)
    sent_ps = np.histogram(S_t, bins)[0]
    recv_ps = np.histogram(R_t, bins)[0]
    ax2.fill_between(bins[:-1], sent_ps, step="post", color=GRID, alpha=0.7, lw=0, label="sent")
    ax2.step(bins[:-1], recv_ps, where="post", color=DELIVERED, lw=2, label="delivered")
    ax2.set_xlim(0, meta["simTime"])
    ax2.set_ylim(0, max(sent_ps.max(), 1) * 1.15)
    ax2.set_ylabel("packets / s", fontsize=8.5, color=INK2)
    ax2.set_xlabel("simulation time (s)", fontsize=8.5, color=INK2)
    ax2.tick_params(labelsize=8, colors=INK2)
    for s in ("top", "right"):
        ax2.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax2.spines[s].set_color(GRID)
    ax2.grid(axis="y", color=GRID, lw=0.6, alpha=0.7)
    ax2.legend(loc="upper right", frameon=False, fontsize=8.5, labelcolor=INK2, ncol=2)
    cursor = ax2.axvline(0, color=INK, lw=1.2)

    title.set_text(f"ns-3 VANET highway · AODV over 802.11p · run {int(meta['run'])}")
    sub.set_text(f"{int(meta['nVehicles'])} vehicles · mean {meta['speed']:g} m/s · "
                 f"{meta['dataRateKbps']:g} kbit/s per flow · {rng:g} m range · 10 UDP flows")

    def at(t):
        i = min(np.searchsorted(times, t), len(times) - 1)
        return xy[i]

    def frame(t):
        p = at(t)
        sx, sy, row = screen(p, meta)
        veh.set_offsets(np.c_[sx, sy])
        sidx = sorted(senders)
        snd.set_offsets(np.c_[sx[sidx], sy[sidx]])
        ridx = sorted(receivers)
        rcv.set_offsets(np.c_[sx[ridx], sy[ridx]])

        lo = t - args.step
        # data hops in this frame window (deduplicated per link)
        if len(D):
            m = (D[:, 0] > lo) & (D[:, 0] <= t) & (D[:, 2] >= 0)
            links = {(int(a), int(b)) for a, b in D[m][:, 1:3]}
        else:
            links = set()
        segs = [arc(sx[a], sy[a], sx[b], sy[b], row[a] == row[b], seg) for a, b in links]
        hops.set_segments(segs)

        cm = (C_t > lo) & (C_t <= t)
        req = [C[i][1] for i in np.nonzero(cm)[0] if C[i][2] == "RREQ"]
        err = [C[i][1] for i in np.nonzero(cm)[0] if C[i][2] == "RERR"]
        rreq.set_offsets(np.c_[sx[req], sy[req]] if req else np.zeros((0, 2)))
        rerr.set_offsets(np.c_[sx[err], sy[err]] + [0, 0.9] if err else np.zeros((0, 2)))
        if len(R):
            rm = (R[:, 0] > lo) & (R[:, 0] <= t)
            got = sorted({int(n) for n in R[rm][:, 1]})
        else:
            got = []
        dlv.set_offsets(np.c_[sx[got], sy[got]] if got else np.zeros((0, 2)))

        n_s = np.searchsorted(S_t, t, side="right")
        n_r = np.searchsorted(R_t, t, side="right")
        pdr = f"{100 * n_r / n_s:5.1f}%" if n_s else "    –"
        n_err = int(np.sum((C_t <= t) & rerr_mask))
        stats.set_text(f"t = {t:5.1f} s   sent {n_s:5d}   delivered {n_r:5d}   PDR {pdr}   RERRs {n_err:4d}")
        cursor.set_xdata([t, t])
        return []

    if args.snapshot:
        frame(float(args.snapshot[0]))
        fig.savefig(args.snapshot[1], dpi=130, facecolor=SURFACE)
        print(f"Wrote {args.snapshot[1]}")

    ts = np.arange(args.start, args.end + 1e-9, args.step)
    anim = animation.FuncAnimation(fig, frame, frames=ts, blit=False)
    if args.out.endswith(".mp4"):
        writer = animation.FFMpegWriter(fps=args.fps, bitrate=2400)
    else:
        writer = animation.PillowWriter(fps=args.fps)
    anim.save(args.out, writer=writer, savefig_kwargs={"facecolor": SURFACE})
    print(f"Wrote {args.out} ({len(ts)} frames, {args.step:g} s of simulation per frame)")


if __name__ == "__main__":
    main()
