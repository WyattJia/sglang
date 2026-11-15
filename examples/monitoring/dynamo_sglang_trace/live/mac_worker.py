import os
from pathlib import Path

import sglang
from aiohttp import web

if __name__ == "__main__":
    engine = sglang.Engine(
        model_path=str(Path("tiny").resolve()),
        disable_cuda_graph=True,
        max_total_tokens=2048,
        max_running_requests=8,
        prefill_max_requests=1,
        enable_trace=True,
        otlp_traces_endpoint="127.0.0.1:4317",
        log_level="warning",
    )

    async def generate(req):
        data = await req.json()
        out = await engine.async_generate(
            input_ids=data["ids"],
            sampling_params={"temperature": 0, "max_new_tokens": 8, "ignore_eos": True},
            rid=data["rid"],
            external_trace_header={"traceparent": req.headers["traceparent"]},
        )
        return web.json_response(
            {
                "rid": out["meta_info"]["id"],
                "tokens": out["meta_info"]["completion_tokens"],
            }
        )

    app = web.Application()
    app.router.add_post("/generate", generate)
    web.run_app(app, host=os.environ["DEMO_BIND"], port=18888)
