"""Show a successful request with positive router wait, admission rejection and forward membership."""

import argparse
import json
from collections import defaultdict
from pathlib import Path

from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import (
    ExportTraceServiceRequest,
)


def join(folder, target):
    spans = defaultdict(list)
    for path in folder.glob("*.pb"):
        message = ExportTraceServiceRequest.FromString(path.read_bytes())
        for rs in message.resource_spans:
            for ss in rs.scope_spans:
                for s in ss.spans:
                    spans[s.trace_id.hex()].append(s)
    waits = defaultdict(list)
    for line in (folder / "frontend.log").read_text(errors="replace").splitlines():
        if "refreshed overlap scores after long queue wait" not in line:
            continue
        try:
            log = json.loads(line)
        except ValueError:
            continue
        fields = log.get("fields", log)
        if "wait_ms" in fields:
            waits[fields.get("request_id")].append(fields["wait_ms"])
    forwards = defaultdict(list)
    for line in (folder / "worker.log").read_text(errors="replace").splitlines():
        if "DEMO_FORWARD " in line:
            row = json.loads(line.split("DEMO_FORWARD ", 1)[1])
            for rid in row["rids"]:
                forwards[rid].append(
                    {k: row[k] for k in ("forward_id", "device", "pid")}
                )
    for req in sorted(
        json.loads((folder / "requests.json").read_text()),
        key=lambda r: -r["elapsed_ms"],
    ):
        tid = req["trace_id"]
        if (target and tid != target) or req["status"] != 200:
            continue
        rids = set()
        reasons = []
        for span in spans[tid]:
            for a in span.attributes:
                if a.key == "rid":
                    rids.add(a.value.string_value)
            for e in span.events:
                if e.name == "prefill_admission_rejection":
                    reasons.append(
                        {
                            a.key: getattr(a.value, a.value.WhichOneof("value"))
                            for a in e.attributes
                        }
                    )
        router = waits[req["router_request_id"]]
        if (
            len(router) == 1
            and router[0] > 0
            and len(rids) == 1
            and reasons
            and forwards[next(iter(rids))]
        ):
            rid = next(iter(rids))
            return {
                "trace_id": tid,
                "request_ms": req["elapsed_ms"],
                "router_request_id": req["router_request_id"],
                "router_wait_ms": router[0],
                "engine_rid": rid,
                "prefill_rejections": reasons,
                "prefill_forwards": forwards[rid],
            }
    raise SystemExit("No successful request has all three observations")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("folder", type=Path)
    p.add_argument("trace_id", nargs="?")
    a = p.parse_args()
    print(json.dumps(join(a.folder, a.trace_id), indent=2))
