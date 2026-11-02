#!/usr/bin/env bash
# Runs one seed of every test point in the four sweeps with tracing on, then
# draws the animations:
#   OUT/netanim/<sweep>_<value>.xml   NetAnim animation of each run (open in NetAnim)
#   OUT/traces/<sweep>_<value>.trace  event trace of each run
#   OUT/<sweep>/<sweep>_<value>.gif   labelled animation of each run
#   OUT/<sweep>_sweep.gif             all values of one sweep side by side
#
# Usage (macOS or Linux):
#   NS3_DIR=~/ns-allinone-3.45/ns-3.45 ./make_animations.sh
# Optional: SEED=1, JOBS=8, OUT=results/animations, PYTHON=python3, and the same
# baseline and sweep variables as run_experiments.sh (BASE_N, DENSITY, ...).
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
NS3_DIR="${NS3_DIR:-$HOME/ns-allinone-3.45/ns-3.45}"
OUT="${OUT:-$HERE/results/animations}"
SEED="${SEED:-1}"
JOBS="${JOBS:-$(nproc 2>/dev/null || sysctl -n hw.ncpu)}"
PYTHON="${PYTHON:-python3}"

BASE_N="${BASE_N:-60}"
BASE_SPEED="${BASE_SPEED:-20}"
BASE_RATE="${BASE_RATE:-100}"
BASE_RANGE="${BASE_RANGE:-150}"
DENSITY="${DENSITY:-20 40 60 80 100}"
SPEED="${SPEED:-10 15 20 25}"
LOAD="${LOAD:-50 100 250 500 750}"
RANGE="${RANGE:-50 100 150 200 250}"

mkdir -p "$OUT/netanim" "$OUT/traces" "$OUT/logs"
OUT="$(cd "$OUT" && pwd)"
cp "$HERE/vanet-highway.cc" "$NS3_DIR/scratch/"
cd "$NS3_DIR"
./ns3 build

# One line per run: sweep value nVehicles speed rate range
{
    for n in $DENSITY; do echo "density $n $n $BASE_SPEED $BASE_RATE $BASE_RANGE"; done
    for s in $SPEED; do echo "speed $s $BASE_N $s $BASE_RATE $BASE_RANGE"; done
    for r in $LOAD; do echo "load $r $BASE_N $BASE_SPEED $r $BASE_RANGE"; done
    for g in $RANGE; do echo "range $g $BASE_N $BASE_SPEED $BASE_RATE $g"; done
} > "$OUT/jobs.txt"

run_one() {
    read -r exp val n speed rate range <<< "$1"
    name="${exp}_${val}"
    rm -f "$OUT/traces/$name.csv"
    if ./ns3 run --no-build "vanet-highway --experiment=$exp --nVehicles=$n --speed=$speed \
--dataRateKbps=$rate --range=$range --RngRun=$SEED --csv=$OUT/traces/$name.csv \
--trace=$OUT/traces/$name.trace --netanim=$OUT/netanim/$name.xml" > "$OUT/logs/$name.log" 2>&1; then
        echo "done   $name"
    else
        echo "FAILED $name (see $OUT/logs/$name.log)"
        return 1
    fi
}
export -f run_one
export OUT SEED

echo "Running $(wc -l < "$OUT/jobs.txt") traced simulations (seed $SEED) with $JOBS in parallel..."
xargs -P "$JOBS" -I{} bash -c 'run_one "$1"' _ {} < "$OUT/jobs.txt"

echo "Drawing the animations..."
draw_one() {
    read -r exp val _ <<< "$1"
    mkdir -p "$OUT/$exp"
    "$PYTHON" "$HERE/animate_trace.py" "$OUT/traces/${exp}_${val}.trace" "$OUT/$exp/${exp}_${val}.gif" \
        --sweep "$exp" --snapshot 30 "$OUT/$exp/${exp}_${val}_t30.png" > /dev/null
    echo "drawn  ${exp}_${val}"
}
export -f draw_one
export HERE PYTHON
xargs -P "$JOBS" -I{} bash -c 'draw_one "$1"' _ {} < "$OUT/jobs.txt"
for exp in density speed load range; do
    "$PYTHON" "$HERE/animate_sweep.py" "$exp" "$OUT/${exp}_sweep.gif" "$OUT"/traces/"${exp}"_*.trace \
        --snapshot 30 "$OUT/${exp}_sweep_t30.png"
done
echo "Animations are in $OUT"
