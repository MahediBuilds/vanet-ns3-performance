#!/usr/bin/env bash
# Runs every test point of the four sweeps with several random seeds.
# Each sweep varies one parameter and keeps the others at the baseline.
#
# Usage (from Ubuntu/WSL):
#   NS3_DIR=~/ns-allinone-3.45/ns-3.45 ./run_experiments.sh
# Optional: SEEDS=5 (runs per test point), JOBS=8 (parallel runs), OUT=results
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
NS3_DIR="${NS3_DIR:-$HOME/ns-allinone-3.45/ns-3.45}"
OUT="$(realpath -m "${OUT:-$HERE/results}")"
SEEDS="${SEEDS:-5}"
JOBS="${JOBS:-$(nproc)}"

# Baseline
BASE_N=60       # vehicles
BASE_SPEED=20   # m/s
BASE_RATE=100   # kbit/s per flow
BASE_RANGE=150  # m

mkdir -p "$OUT/raw" "$OUT/logs"
cp "$HERE/vanet-highway.cc" "$NS3_DIR/scratch/"
cd "$NS3_DIR"
./ns3 build

# One line per run: experiment value nVehicles speed rate range seed
add() {
    for run in $(seq 1 "$SEEDS"); do
        echo "$1 $2 $3 $4 $5 $6 $run"
    done
}
{
    for n in 20 40 60 80 100; do add density "$n" "$n" $BASE_SPEED $BASE_RATE $BASE_RANGE; done
    for s in 10 15 20 25; do add speed "$s" $BASE_N "$s" $BASE_RATE $BASE_RANGE; done
    for r in 50 100 250 500 750; do add load "$r" $BASE_N $BASE_SPEED "$r" $BASE_RANGE; done
    for g in 50 100 150 200 250; do add range "$g" $BASE_N $BASE_SPEED $BASE_RATE "$g"; done
} > "$OUT/jobs.txt"

run_one() {
    read -r exp val n speed rate range run <<< "$1"
    name="${exp}_${val}_run${run}"
    csv="$OUT/raw/$name.csv"
    # Skip runs that already finished, so an interrupted batch can be resumed.
    [ -s "$csv" ] && return 0
    if ./ns3 run --no-build "vanet-highway --experiment=$exp --nVehicles=$n --speed=$speed \
--dataRateKbps=$rate --range=$range --RngRun=$run --csv=$csv" > "$OUT/logs/$name.log" 2>&1; then
        echo "done   $name"
    else
        echo "FAILED $name (see $OUT/logs/$name.log)"
        return 1
    fi
}
export -f run_one
export OUT

echo "Running $(wc -l < "$OUT/jobs.txt") simulations with $JOBS in parallel..."
xargs -P "$JOBS" -I{} bash -c 'run_one "$1"' _ {} < "$OUT/jobs.txt"
echo "All runs finished. Results are in $OUT/raw"
echo "Make the graphs with: python3 $HERE/plot_results.py $OUT"
