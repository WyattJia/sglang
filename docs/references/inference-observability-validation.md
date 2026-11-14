# Request tracing and GPU profiling in this fork

Two opt-in features help investigate inference latency at different levels.

* [Prefill admission tracing](https://github.com/sgl-project/sglang/pull/50539) records the request-count or input-token limit that deferred a sampled request. Enable request tracing at level 3 and set `SGLANG_TRACE_PREFILL_ADMISSION=1` to export the first rejection per reason through OpenTelemetry.
* [Kernel coverage and forward attribution](https://github.com/sgl-project/sglang/pull/50540) analyzes an existing Torch profiler capture. Set `SGLANG_PROFILE_STEP_KERNELS=1` before starting the engine and capture CPU and GPU activities. Each device summary reports the union of observed kernel intervals. The compact trace links kernels to annotated forwards through unique CPU launch correlations and reports unmatched kernels.

## Single-GPU Engine validation

A two-layer FP16 Llama ran through the Engine Python API on a Colab G4 RTX PRO 6000 Blackwell with CUDA 13.0 and PyTorch 2.14.1+cu130. The OTLP HTTP receiver collected ten zero-duration admission spans for the per-pass request limit. The input-token limit has CPU test coverage.

| Capture | Observed kernels | Matched kernels | Annotated forwards | Observed kernel busy time |
|---|---:|---:|---:|---:|
| Eager | 420 | 327 | 7 | 707,307 ns |
| CUDA Graph | 1,030 | 778 | 24 | 1,601,824 ns |

Independent interval unions from both raw captures agreed with the summaries. A 174.77 MiB decompressed capture exceeded the 16 MiB inline input limit. The engine accepted another generation after profiling stopped. Offline analysis recovered 6,618 kernel records and 55 annotated forwards:

```sh
python -m sglang.srt.observability.kernel_profile capture.trace.json.gz --steps > summary.json
```

The captures validate correctness on one GPU. Production overhead, multi-rank attribution and a request timeline spanning a router and an inference worker remain open.
