from pathlib import Path

p = Path("src/python/sglang/srt/hardware_backend/mlx/scheduler_mixin.py")
s = p.read_text()
a = "        result = self.tp_worker.finalize_mlx_result(pending.launch, pending.reqs)"
assert s.count(a) == 1
if "DEMO_FORWARD " not in s:
    p.write_text(
        s.replace(
            a,
            a
            + """
        if pending.batch_copy.forward_mode.is_extend():
            import os, json
            print("DEMO_FORWARD " + json.dumps({"forward_id":pending.batch_copy.forward_iter,"pid":os.getpid(),"device":"metal:0","rids":[r.rid for r in pending.reqs]}), flush=True)""",
        )
    )
