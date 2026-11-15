"""Export only the interview sample fields from a complete local capture."""

import argparse
import json
from pathlib import Path

from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import (
    ExportTraceServiceRequest,
)
from show_trace import join


def extract(raw, dest, trace_id):
    match = join(raw, trace_id)
    tid = match["trace_id"]
    (client,) = (
        r
        for r in json.loads((raw / "requests.json").read_text())
        if r["trace_id"] == tid
    )
    rows = {
        "client": [
            {
                "trace_id": tid,
                "request_id": "request-1",
                "elapsed_ms": client["elapsed_ms"],
                "http_status": client["status"],
                "output_tokens": json.loads(client["response"])["tokens"],
            }
        ],
        "router": [{"request_id": "request-1", "wait_ms": match["router_wait_ms"]}],
        "engine_root": [],
        "admission": [],
        "forward": [],
    }
    for path in raw.glob("*.pb"):
        msg = ExportTraceServiceRequest.FromString(path.read_bytes())
        for resource in msg.resource_spans:
            for scope in resource.scope_spans:
                for span in scope.spans:
                    if span.trace_id.hex() != tid:
                        continue
                    if any(
                        a.key == "rid" and a.value.string_value == match["engine_rid"]
                        for a in span.attributes
                    ):
                        rows["engine_root"].append({"trace_id": tid, "rid": "engine-1"})
                    for event in span.events:
                        if event.name == "prefill_admission_rejection":
                            attrs = {
                                a.key: getattr(a.value, a.value.WhichOneof("value"))
                                for a in event.attributes
                                if a.key
                                in {
                                    "reason",
                                    "selected_requests",
                                    "max_requests",
                                    "remaining_input_tokens",
                                    "input_tokens",
                                }
                            }
                            rows["admission"].append(
                                {
                                    "trace_id": tid,
                                    "event": {"name": event.name, **attrs},
                                }
                            )
    for fwd in match["prefill_forwards"]:
        rows["forward"].append(
            {
                "rid": "engine-1",
                "device": fwd["device"],
                "forward_iter": fwd["forward_id"],
            }
        )
    if any(len(records) != 1 for records in rows.values()):
        raise ValueError(
            "Choose a trace with one admission event and one prefill forward for this example"
        )
    dest.mkdir(parents=True, exist_ok=True)
    for kind, records in rows.items():
        (dest / f"{kind}.json").write_text(json.dumps(records, indent=2) + "\n")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("raw", type=Path)
    p.add_argument("dest", type=Path)
    p.add_argument("trace_id")
    args = p.parse_args()
    extract(args.raw, args.dest, args.trace_id)
