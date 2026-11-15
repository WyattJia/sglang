import asyncio
import json
import os
import time
import uuid
from pathlib import Path

import aiohttp
from dynamo._core import (
    DistributedRuntime,
    KvRouter,
    KvRouterConfig,
    ModelInput,
    ModelRuntimeConfig,
    ModelType,
    WorkerType,
    register_model,
)


async def main():
    rt = DistributedRuntime(asyncio.get_running_loop(), "file", "tcp")
    ep = rt.endpoint(f"demo-{uuid.uuid4().hex[:8]}.mlx.generate")
    cfg = ModelRuntimeConfig()
    cfg.max_num_batched_tokens = 128
    cfg.max_num_seqs = 8
    cfg.total_kv_blocks = 512
    cfg.context_length = 2048
    await register_model(
        ModelInput.Tensor,
        ModelType.TensorBased,
        ep,
        "mlx-demo",
        worker_type=WorkerType.Aggregated,
        runtime_config=cfg,
        kv_cache_block_size=4,
        tensor_model_config={"name": "mlx-demo", "inputs": [], "outputs": []},
    )

    async def service(req, ctx=None):
        async with (
            aiohttp.ClientSession() as http,
            http.post(
                f"http://{os.environ['DEMO_BIND']}:18888/generate",
                json={"rid": req["rid"], "ids": req["ids"]},
                headers={"traceparent": req["traceparent"]},
            ) as resp,
        ):
            yield {"status": resp.status, "body": await resp.text()}

    task = asyncio.ensure_future(ep.serve_endpoint(service))
    cli = await ep.client()
    workers = await cli.wait_for_instances()
    print("WORKERS", workers, flush=True)
    router = KvRouter(
        ep, 4, KvRouterConfig(use_kv_events=False, router_queue_threshold=0.75)
    )
    await asyncio.sleep(1)

    async def one(i):
        tid = uuid.uuid4().hex
        rid = str(uuid.uuid4())
        ids = [3, 4] * 16 + [5 + i % 15]
        start = time.monotonic_ns()
        worker, _rank, _ = await router.best_worker(ids, request_id=rid)
        routed = time.monotonic_ns()
        assert worker in workers, (worker, workers)
        try:
            stream = await cli.direct(
                {
                    "ids": ids,
                    "rid": rid,
                    "traceparent": f"00-{tid}-{uuid.uuid4().hex[:16]}-01",
                },
                worker,
                annotated=False,
            )
            replies = [reply async for reply in stream]
            assert len(replies) == 1, replies
            return {
                "trace_id": tid,
                "router_request_id": rid,
                "status": replies[0]["status"],
                "elapsed_ms": (time.monotonic_ns() - start) / 1e6,
                "selection_ms": (routed - start) / 1e6,
                "worker": worker,
                "response": replies[0]["body"],
            }
        finally:
            await router.mark_prefill_complete(rid)
            await router.free(rid)

    rows = await asyncio.gather(*(one(i) for i in range(32)))
    Path("/demo/results/requests.json").write_text(json.dumps(rows, indent=2))
    rt.shutdown()
    await task


asyncio.run(asyncio.wait_for(main(), 60))
