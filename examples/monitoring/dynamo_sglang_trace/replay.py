"""Join the public evidence extracts for one request, offline."""

import argparse
import json
from pathlib import Path


def replay(folder, trace_id):
    def one(kind, key, value):
        matches = [
            row
            for row in json.loads((folder / f"{kind}.json").read_text())
            if row[key] == value
        ]
        if len(matches) != 1:
            raise ValueError(
                f"{kind}: expected one matching record, found {len(matches)}"
            )
        return matches[0]

    client = one("client", "trace_id", trace_id)
    router = one("router", "request_id", client["request_id"])
    root = one("engine_root", "trace_id", trace_id)
    decision = one("admission", "trace_id", trace_id)
    forward = one("forward", "rid", root["rid"])
    return {
        "trace_id": trace_id,
        "client": client,
        "router_wait_ms": router["wait_ms"],
        "prefill_rejection": decision["event"],
        "prefill_forward": forward,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("trace_id")
    args = parser.parse_args()
    try:
        print(
            json.dumps(
                replay(Path(__file__).resolve().parent / "evidence", args.trace_id),
                indent=2,
            )
        )
    except ValueError as exc:
        parser.exit(1, f"{exc}\n")
