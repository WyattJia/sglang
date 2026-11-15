#!/usr/bin/env bash
set -euo pipefail
here=$(cd "$(dirname "$0")" && pwd)
repo=$(git -C "$here" rev-parse --show-toplevel)
run_dir=$(mktemp -d "${TMPDIR:-/tmp}/sglang-trace.XXXXXXXX")
cd "$run_dir"
echo "Capture directory: $PWD"
name="sglang-trace-$$"
worker_pid=""
receiver_pid=""
created=""
cleanup() {
    if [[ -n "$created" ]]; then
        container stop "$name" >/dev/null || true
        container delete "$name" >/dev/null || true
    fi
    if [[ -n "$worker_pid" ]]; then kill -TERM "$worker_pid" 2>/dev/null || true; fi
    if [[ -n "$receiver_pid" ]]; then kill -TERM "$receiver_pid" 2>/dev/null || true; fi
}
trap cleanup EXIT
mkdir src results
git -C "$repo" archive 587f068171 python | tar -x -C src
cp "$here"/*.py "$here"/requirements-*.txt .
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python -r requirements-mac.txt
.venv/bin/python make_model.py
.venv/bin/python instrument_mlx.py
container run -d --name "$name" -v "$PWD:/demo" python:3.12-slim sleep 3600
created=1
export DEMO_BIND
DEMO_BIND=$(container exec "$name" python -c 'import socket,struct; print(next(socket.inet_ntoa(struct.pack("<I",int(row.split()[2],16))) for row in open("/proc/net/route") if row.split()[1]=="00000000"))')
container exec "$name" pip install -r /demo/requirements-linux.txt
.venv/bin/python receiver.py >results/collector.log 2>&1 &
receiver_pid=$!
PYTHONPATH="$PWD/src/python" SGLANG_USE_MLX=1 SGLANG_TRACE_PREFILL_ADMISSION=1 .venv/bin/python mac_worker.py >results/worker.log 2>&1 &
worker_pid=$!
url="http://$DEMO_BIND:18888/generate"
ready=""
for _ in {1..120}; do
    kill -0 "$receiver_pid" "$worker_pid"
    if [[ $(curl --noproxy '*' --max-time 1 -s -o /dev/null -w '%{http_code}' "$url") == 405 ]]; then ready=1; break; fi
    sleep 1
done
[[ -n "$ready" ]] || { echo "Worker startup failed: $PWD/results/worker.log" >&2; exit 1; }
container exec --env "DEMO_BIND=$DEMO_BIND" "$name" sh -c 'cd /demo && DYN_EVENT_PLANE=zmq DYN_LOGGING_JSONL=1 DYN_ROUTER_OVERLAP_REFRESH_AFTER_SECS=0.000001 DYN_ROUTER_MIN_INITIAL_WORKERS=1 python route.py >results/frontend.log 2>&1'
for _ in {1..20}; do
    if .venv/bin/python show_trace.py results >results/selected.json; then
        cat results/selected.json
        exit 0
    fi
    sleep 1
done
exit 1
