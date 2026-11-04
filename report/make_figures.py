"""Figures for the VANET report, drawn in the same style as the reference report
(serif text, grey / blue / orange bars with black edges, value labels)."""
import csv
import os
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Rectangle, Circle

PROJ = sys.argv[1]
OUT = sys.argv[2]
os.makedirs(OUT, exist_ok=True)

plt.rcParams.update({
    "font.family": "serif",
    "font.serif": ["Times New Roman", "Times", "DejaVu Serif"],
    "font.size": 10,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.titlesize": 11,
    "savefig.dpi": 220,
})
GREY, BLUE, ORANGE, GREEN, RED = "#8c8c8c", "#6b8cba", "#c0622b", "#4f9a55", "#b5403a"
LIGHT = "#eeeeee"


def save(fig, name):
    fig.savefig(os.path.join(OUT, name), bbox_inches="tight", facecolor="white")
    plt.close(fig)


def read(path):
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


summary = {(r["experiment"], float(r["x"])): r for r in read(os.path.join(PROJ, "results/summary.csv"))}
opt = {r["experiment"]: r for r in read(os.path.join(PROJ, "results/optimal/summary.csv"))}
opt_runs = read(os.path.join(PROJ, "results/optimal/all_runs.csv"))


def box(ax, x, y, w, h, text, fc="white", ec="black", fs=9, bold=False, style="round,pad=0.02"):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle=style, fc=fc, ec=ec, lw=1))
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=fs,
            fontweight="bold" if bold else "normal", wrap=True)


def arrow(ax, p, q, color="black", ls="-", lw=1.1, style="-|>", rad=0.0):
    ax.add_patch(FancyArrowPatch(p, q, arrowstyle=style, mutation_scale=11, color=color, lw=lw,
                                 linestyle=ls, connectionstyle=f"arc3,rad={rad}"))


# ---------------------------------------------------------------- Fig: scenario
def fig_scenario():
    fig, ax = plt.subplots(figsize=(9, 3.9))
    ax.set_xlim(-150, 2150)
    ax.set_ylim(-40, 62)
    ax.axis("off")
    ax.add_patch(Rectangle((-130, -36), 2260, 92, fill=False, ls="--", ec="#777777", lw=1))
    ax.text(-115, 51, "Highway 2000 m, 4 lanes (2 per direction, 5 m apart), 60 vehicles (baseline), "
                      "AODV over IEEE 802.11p, 10 UDP flows", fontsize=9, fontweight="bold", va="center")
    ax.add_patch(Rectangle((0, -2), 2000, 20, fc="#e9e8e3", ec="none"))
    ax.plot([0, 2000], [8, 8], color="#d4a72c", lw=1.2)
    for yl in (3, 13):
        ax.plot([0, 2000], [yl, yl], color="white", lw=0.8, ls=(0, (6, 6)))
    rng = np.random.default_rng(3)
    lane_y = [0.6, 5.4, 10.6, 15.4]
    xs = [(rng.uniform(15, 1985), lane_y[i % 4]) for i in range(60)]
    # one illustrated flow: sender at ~250 m, receiver at ~820 m, relays in between
    s_x, d_x = 260, 830
    relays = [430, 600]
    for i, (x, y) in enumerate(xs):
        if min(abs(x - v) for v in [s_x, d_x] + relays) < 25:
            continue
        ax.add_patch(Rectangle((x - 9, y - 1.4), 18, 2.8, fc=GREY, ec="black", lw=0.4))
    pts = [(s_x, 0.6, ORANGE), (relays[0], 10.6, GREY), (relays[1], 5.4, GREY), (d_x, 15.4, GREEN)]
    for x, y, c in pts:
        ax.add_patch(Rectangle((x - 9, y - 1.4), 18, 2.8, fc=c, ec="black", lw=0.6))
    for (x1, y1, _), (x2, y2, _) in zip(pts[:-1], pts[1:]):
        ax.add_patch(FancyArrowPatch((x1, 20), (x2, 20), arrowstyle="-|>", mutation_scale=10,
                                     connectionstyle="arc3,rad=-0.35", color=BLUE, lw=1.2))
    ax.text((s_x + d_x) / 2, 37, "multi-hop AODV route: sender -> relay -> relay -> receiver", ha="center",
            fontsize=8, color=BLUE)
    # communication range of one vehicle, drawn along the road
    cx = 1500
    ax.add_patch(Rectangle((cx - 9, 10.6 - 1.4), 18, 2.8, fc=GREY, ec="black", lw=0.6))
    ax.annotate("", xy=(cx - 150, 25), xytext=(cx + 150, 25),
                arrowprops=dict(arrowstyle="<->", color=BLUE, lw=1.1))
    ax.plot([cx, cx], [12, 25], color=BLUE, lw=0.8, ls=":")
    ax.text(cx, 29, "range r = 150 m each way (hard cut-off)", ha="center", fontsize=8, color=BLUE)
    ax.annotate("", xy=(2105, 3), xytext=(2030, 3), arrowprops=dict(arrowstyle="-|>", color="black"))
    ax.text(2068, -4, "east", ha="center", fontsize=8)
    ax.annotate("", xy=(-105, 13), xytext=(-30, 13), arrowprops=dict(arrowstyle="-|>", color="black"))
    ax.text(-68, 17, "west", ha="center", fontsize=8)
    ax.add_patch(FancyArrowPatch((1990, -6), (10, -6), arrowstyle="-|>", mutation_scale=10,
                                 connectionstyle="arc3,rad=0.04", color="#555555", lw=1, ls="--"))
    ax.text(1000, -22, "a vehicle leaving one end re-enters at the other end, so the density stays constant",
            ha="center", fontsize=8, color="#333333")
    for xt in (0, 500, 1000, 1500, 2000):
        ax.text(xt, -32, f"{xt} m", ha="center", fontsize=7.5, color="#555555")
    hs = [Rectangle((0, 0), 1, 1, fc=c, ec="black", lw=0.4) for c in (GREY, ORANGE, GREEN)]
    ax.legend(hs, ["vehicle (can relay)", "flow sender", "flow receiver"], loc="upper right", fontsize=8,
              frameon=False, ncol=3, bbox_to_anchor=(0.99, 0.88))
    save(fig, "fig_scenario.png")


# ---------------------------------------------------------------- Fig: node architecture
def fig_architecture():
    fig, ax = plt.subplots(figsize=(8.6, 5.0))
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 64)
    ax.axis("off")
    layers = [
        ("Application", "OnOffApplication\n(constant-rate UDP, 512 B)", "PacketSink\n(UDP port 9000+f)"),
        ("Transport", "UDP socket (Send)", "UDP socket (Recv callback)"),
        ("Network", "IPv4 + AODV (RREQ, RREP, RERR,\nHELLO on UDP port 654)", None),
        ("MAC", "WifiNetDevice, AdhocWifiMac,\nConstantRateWifiManager", None),
        ("PHY", "YansWifiPhy, 802.11p, 10 MHz,\nOFDM 6 Mbit/s, 20 dBm", None),
    ]
    for side, x0 in (("Sender vehicle", 4), ("Receiver vehicle", 56)):
        ax.text(x0 + 20, 61, side, ha="center", fontsize=10, fontweight="bold")
        for i, (name, a, b) in enumerate(layers):
            y = 50 - i * 9
            label = a if (b is None or side.startswith("Sender")) else b
            fc = "#f6e3d8" if i == 0 else ("#e3ebf5" if i in (1, 2) else LIGHT)
            box(ax, x0, y, 40, 7.4, "", fc=fc)
            ax.text(x0 + 2, y + 3.7, name, va="center", fontsize=8, fontweight="bold")
            ax.text(x0 + 25, y + 3.7, label, va="center", ha="center", fontsize=7.6)
            if i:
                arrow(ax, (x0 + 20, y + 9), (x0 + 20, y + 7)) if side.startswith("Sender") else \
                    arrow(ax, (x0 + 20, y + 7), (x0 + 20, y + 9))
    # channel
    box(ax, 4, 2, 92, 7, "YansWifiChannel: ConstantSpeedPropagationDelay + RangePropagationLossModel "
                         "(MaxRange = r)",
        fc="#fbf3d6", fs=8)
    arrow(ax, (24, 14), (24, 9))
    arrow(ax, (76, 9), (76, 14))
    # relay
    box(ax, 46, 13.5, 8, 14, "relay\nvehicles\n(AODV\nforward)", fc="white", fs=7)
    arrow(ax, (44, 23), (46, 23), color=BLUE)
    arrow(ax, (54, 23), (56, 23), color=BLUE)
    # flow monitor + mobility
    ax.text(50, 58.5, "FlowMonitor\n(per-flow tx, rx, delay)", ha="center", fontsize=7.6, color=ORANGE,
            bbox=dict(boxstyle="round", fc="white", ec=ORANGE))
    arrow(ax, (44.5, 57), (44, 35.5), color=ORANGE, ls="--", rad=0.25)
    arrow(ax, (55.5, 57), (56, 35.5), color=ORANGE, ls="--", rad=-0.25)
    ax.text(50, 10.6, "mobility: ConstantVelocityMobilityModel + WrapPositions (every 0.1 s)", ha="center",
            fontsize=7.6, style="italic")
    save(fig, "fig_architecture.png")


# ---------------------------------------------------------------- Fig: workflow
def fig_workflow():
    fig, ax = plt.subplots(figsize=(8.6, 3.6))
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 40)
    ax.axis("off")
    steps = [
        ("run_experiments.sh", "4 sweeps x 5 seeds\n= 95 jobs, run in\nparallel (xargs -P)", "#f6e3d8"),
        ("vanet-highway.cc", "one ns-3 run per job\n(100 s simulated)\nFlowMonitor stats", "#e3ebf5"),
        ("results/raw/*.csv", "one CSV row per run:\nPDR, delay,\nthroughput, loss", LIGHT),
        ("plot_results.py", "merge runs, mean and\nstd per test point,\ndraw 4 graphs", "#e3ebf5"),
        ("Optimal search", "best value of each\nfactor, combined run,\nleave-one-out check", "#f6e3d8"),
    ]
    w, gap = 17, 3.2
    for i, (title, body, fc) in enumerate(steps):
        x = 1 + i * (w + gap)
        box(ax, x, 13, w, 18, "", fc=fc)
        ax.text(x + w / 2, 27.5, title, ha="center", va="center", fontsize=8.6, fontweight="bold")
        ax.text(x + w / 2, 19.5, body, ha="center", va="center", fontsize=7.8)
        if i < len(steps) - 1:
            arrow(ax, (x + w, 22), (x + w + gap, 22))
    ax.text(50, 5, "Optional: make_animations.sh runs one seed of every test point with --trace and --netanim; "
                   "animate_trace.py / animate_sweep.py draw the GIFs and snapshots.",
            ha="center", fontsize=7.8, style="italic")
    save(fig, "fig_workflow.png")


# ---------------------------------------------------------------- Fig: flowchart of a run
def fig_flowchart():
    fig, ax = plt.subplots(figsize=(6.4, 8.4))
    ax.set_xlim(0, 60)
    ax.set_ylim(0, 100)
    ax.axis("off")
    items = [
        ("Start: parse command line\n(nVehicles, speed, rate, range, RngRun)", "round"),
        ("Create N vehicles; random x on 2 km, lane i mod 4;\nspeed = v x U(0.8, 1.2), direction by lane", "square"),
        ("Install 802.11p PHY, ad hoc MAC, range-limited channel;\nIPv4 + AODV; addresses 10.1.0.0/16", "square"),
        ("Pick 10 distinct senders and random receivers;\nOnOff -> PacketSink, start 10-11 s, stop 95 s", "square"),
        ("Install FlowMonitor; schedule WrapPositions every 0.1 s", "square"),
        ("Simulator::Run() until 100 s", "square"),
        ("For each FlowMonitor flow:\nUDP and data port?", "diamond"),
        ("Add tx, rx, delay sum and throughput of the flow", "square"),
        ("Compute PDR, delay, throughput, loss;\nappend one row to the CSV file", "square"),
        ("End", "round"),
    ]
    ys = np.linspace(94, 5, len(items))
    for (t, kind), y in zip(items, ys):
        if kind == "diamond":
            ax.add_patch(plt.Polygon([[30, y + 5], [52, y], [30, y - 5], [8, y]], fc="#fbf3d6", ec="black", lw=1))
            ax.text(30, y, t, ha="center", va="center", fontsize=8)
        else:
            box(ax, 6, y - 3.6, 48, 7.2, t, fc="#e3ebf5" if kind == "square" else "#f6e3d8", fs=8,
                style="round,pad=0.3" if kind == "round" else "square,pad=0.02")
    for a, b in zip(ys[:-1], ys[1:]):
        top = b + (5 if abs(b - ys[6]) < 1e-6 else 3.6)
        bot = a - (5 if abs(a - ys[6]) < 1e-6 else 3.6)
        arrow(ax, (30, bot), (30, top))
    ax.text(32, ys[6] - 6.0, "yes", fontsize=8)
    # "no" branch: skip AODV control flows
    ax.plot([52, 57], [ys[6], ys[6]], color="black", lw=1)
    ax.plot([57, 57], [ys[6], ys[8] + 6], color="black", lw=1)
    arrow(ax, (57, ys[8] + 6), (54, ys[8] + 2.5))
    ax.text(53, ys[6] + 1.2, "no (AODV)", fontsize=8)
    save(fig, "fig_flowchart.png")


# ---------------------------------------------------------------- Fig: sequence diagram
def fig_sequence():
    fig, ax = plt.subplots(figsize=(8.4, 6.0))
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.axis("off")
    cols = {"Sender S\n(OnOff app)": 10, "Relay A": 36, "Relay B": 62, "Receiver D\n(PacketSink)": 88}
    for name, x in cols.items():
        box(ax, x - 9, 90, 18, 8, name, fc="#e3ebf5", fs=8.5)
        ax.plot([x, x], [6, 90], color="#999999", lw=0.9, ls="--")
    S, A, B, D = cols.values()

    def msg(y, a, b, text, color="black", ls="-"):
        arrow(ax, (a, y), (b, y), color=color, ls=ls)
        ax.text((a + b) / 2, y + 1.3, text, ha="center", fontsize=7.6, color=color)

    ax.text(1, 85, "t = 10-11 s: first data packet, no route yet; packet is buffered", fontsize=7.8, style="italic")
    msg(80, S, A, "RREQ (broadcast)", BLUE)
    msg(76, A, B, "RREQ (rebroadcast)", BLUE)
    msg(72, B, D, "RREQ (rebroadcast)", BLUE)
    msg(66, D, B, "RREP (unicast)", GREEN)
    msg(62, B, A, "RREP", GREEN)
    msg(58, A, S, "RREP: route S-A-B-D installed", GREEN)
    for y in (52, 48):
        msg(y, S, A, "UDP data 512 B")
        msg(y - 0.0, A, B, "")
        msg(y - 0.0, B, D, "")
    ax.text(D + 1.5, 49.5, "Recv callback,\nFlowMonitor rx", fontsize=7.4)
    ax.text(1, 42, "vehicles move: A and B drive out of range r of each other", fontsize=7.8, style="italic")
    msg(36, A, B, "data frame lost (no MAC ACK)", RED, "--")
    msg(31, A, S, "RERR: route to D broken", RED)
    msg(25, S, A, "new RREQ ... new route found", BLUE)
    msg(19, S, A, "data resumes over new route")
    msg(19, A, B, "")
    msg(19, B, D, "")
    ax.text(1, 11, "HELLO messages (one-hop RREP broadcasts, every 1 s) keep the neighbour tables up to date.",
            fontsize=7.8, style="italic")
    save(fig, "fig_sequence.png")


# ---------------------------------------------------------------- Fig: factor effect (best vs worst)
def fig_factor_effect():
    factors = [("Density", "density", [20, 40, 60, 80, 100], "veh."),
               ("Speed", "speed", [10, 15, 20, 25], "m/s"),
               ("Load", "load", [50, 100, 250, 500, 750], "kbit/s"),
               ("Range", "range", [50, 100, 150, 200, 250], "m")]
    fig, ax = plt.subplots(figsize=(7.6, 3.6))
    base = float(summary[("density", 60.0)]["pdr_mean"])
    xs = np.arange(len(factors))
    lo, hi, lo_lab, hi_lab = [], [], [], []
    for _, e, vals, u in factors:
        p = {v: float(summary[(e, float(v))]["pdr_mean"]) for v in vals}
        vb, vw = max(p, key=p.get), min(p, key=p.get)
        lo.append(p[vw]); hi.append(p[vb]); lo_lab.append(f"{vw:g} {u}"); hi_lab.append(f"{vb:g} {u}")
    b1 = ax.bar(xs - 0.2, lo, 0.38, color=GREY, ec="black", lw=0.6, label="worst tested value")
    b2 = ax.bar(xs + 0.2, hi, 0.38, color=ORANGE, ec="black", lw=0.6, label="best tested value")
    for bars, labs in ((b1, lo_lab), (b2, hi_lab)):
        for r, lab in zip(bars, labs):
            ax.text(r.get_x() + r.get_width() / 2, r.get_height() + 0.8, f"{r.get_height():.1f}\n({lab})",
                    ha="center", fontsize=7.6)
    ax.axhline(base, color=BLUE, ls="--", lw=1, label=f"baseline ({base:.1f}%)", zorder=0)
    ax.set_xticks(xs, [f[0] for f in factors])
    ax.set_ylabel("Packet delivery ratio (%)")
    ax.set_ylim(0, 72)
    ax.set_title("PDR at the worst and best tested value of each factor (5 seeds)")
    ax.legend(frameon=False, fontsize=8, loc="upper left", ncol=3)
    save(fig, "fig_factor_effect.png")


# ---------------------------------------------------------------- Fig: plots2 composite
def fig_plots2():
    from PIL import Image
    names = ["density_vs_pdr", "speed_vs_delay", "load_vs_throughput", "range_vs_pdr"]
    ims = [Image.open(os.path.join(PROJ, "results/plots2", n + ".png")).convert("RGB") for n in names]
    w, h = ims[0].size
    m = Image.new("RGB", (w * 2, h * 2), "white")
    for i, im in enumerate(ims):
        m.paste(im, ((i % 2) * w, (i // 2) * h))
    m.save(os.path.join(OUT, "fig_plots2.png"))


# ---------------------------------------------------------------- Fig: optimal vs baseline
def fig_optimal():
    b, o = opt["baseline"], opt["optimal"]
    fig, axs = plt.subplots(1, 3, figsize=(9.2, 3.4))
    specs = [("pdr", "Packet delivery ratio (%)", "PDR"), ("delayMs", "Average end-to-end delay (ms)", "Delay"),
             ("lossRate", "Packet loss rate (%)", "Packet loss")]
    for ax, (m, yl, title) in zip(axs, specs):
        vals = [float(b[m + "_mean"]), float(o[m + "_mean"])]
        errs = [float(b[m + "_std"]), float(o[m + "_std"])]
        bars = ax.bar([0, 1], vals, 0.55, yerr=errs, capsize=4, color=[GREY, ORANGE], ec="black", lw=0.6)
        for r, v in zip(bars, vals):
            ax.text(r.get_x() + r.get_width() / 2, v / 2, f"{v:.1f}", ha="center", va="center", fontsize=9,
                    color="white", fontweight="bold")
        ax.set_xticks([0, 1], ["Baseline\n60 veh, 20 m/s,\n100 kbit/s, 150 m", "Optimal\n80 veh, 10 m/s,\n50 kbit/s, 250 m"],
                      fontsize=7.6)
        ax.set_ylabel(yl)
        ax.set_title(title)
        if m == "pdr":
            ax.axhline(70, color=BLUE, ls="--", lw=1)
            ax.text(1.32, 71.5, "multiplicative\nestimate ~71%", color=BLUE, fontsize=7.2, ha="right")
            ax.set_ylim(0, 85)
    fig.suptitle("Baseline and optimal configuration, mean and standard deviation over 10 seeds", fontsize=10)
    fig.tight_layout()
    save(fig, "fig_optimal.png")


# ---------------------------------------------------------------- Fig: per-seed
def fig_per_seed():
    fig, ax = plt.subplots(figsize=(7.2, 3.3))
    for e, c, lab, off in (("baseline", GREY, "Baseline", -0.17), ("optimal", ORANGE, "Optimal", 0.17)):
        rs = sorted([r for r in opt_runs if r["experiment"] == e], key=lambda r: int(r["run"]))
        x = np.array([int(r["run"]) for r in rs])
        y = [float(r["pdr"]) for r in rs]
        ax.bar(x + off, y, 0.34, color=c, ec="black", lw=0.5, label=lab)
    ax.set_xticks(range(1, 11))
    ax.set_xlabel("Random seed (--RngRun)")
    ax.set_ylabel("Packet delivery ratio (%)")
    ax.set_ylim(0, 75)
    ax.set_title("PDR of every run: the optimal configuration wins on every seed")
    ax.legend(frameon=False, fontsize=8, ncol=2, loc="upper left")
    save(fig, "fig_per_seed.png")


# ---------------------------------------------------------------- Fig: leave-one-out
def fig_loo():
    order = [("optimal", "Optimal\n(all four best)"), ("loo_density", "Density\n80 -> 60"),
             ("loo_speed", "Speed\n10 -> 20 m/s"), ("loo_load", "Load\n50 -> 100"),
             ("loo_range", "Range\n250 -> 150 m"), ("baseline", "Baseline\n(all four)")]
    fig, ax = plt.subplots(figsize=(8.2, 3.6))
    vals = [float(opt[k]["pdr_mean"]) for k, _ in order]
    errs = [float(opt[k]["pdr_std"]) for k, _ in order]
    cols = [ORANGE, BLUE, BLUE, BLUE, BLUE, GREY]
    bars = ax.bar(range(len(order)), vals, 0.6, yerr=errs, capsize=4, color=cols, ec="black", lw=0.6)
    for r, v in zip(bars, vals):
        ax.text(r.get_x() + r.get_width() / 2, v / 2, f"{v:.1f}", ha="center", va="center", color="white",
                fontsize=9, fontweight="bold")
    ax.set_xticks(range(len(order)), [l for _, l in order], fontsize=8)
    ax.set_ylabel("Packet delivery ratio (%)")
    ax.set_ylim(0, 80)
    ax.set_title("Leave-one-out check: one factor put back to its baseline value (10 seeds)")
    save(fig, "fig_loo.png")


for f in (fig_scenario, fig_architecture, fig_workflow, fig_flowchart, fig_sequence, fig_factor_effect,
          fig_plots2, fig_optimal, fig_per_seed, fig_loo):
    f()
    print("drew", f.__name__)
