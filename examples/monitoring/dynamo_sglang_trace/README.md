# 用一个 trace ID 解释一次慢请求

**一次请求耗时 538.05 ms，其中 516 ms 花在 Dynamo Router 等待。** 请求进入 SGLang 后，又遇到一次 Prefill 准入限制，最终在 Apple Metal 的第 222 轮 Prefill forward 中执行，返回 8 个 token。

从仓库根目录运行下面这条命令。回放只需要 Python 3 标准库，可离线运行。

```sh
python3 examples/monitoring/dynamo_sglang_trace/replay.py 330e69c310844132864ab970585a89c9
```

## 顺着证据讲这条请求

| 面试时要回答的问题 | 查到的记录 | 关联方式 |
|---|---|---|
| 请求有多慢？ | [客户端](evidence/client.json)记录 HTTP 200、8 个输出 token 和 538.05 ms | 以 trace ID 查客户端记录 |
| 时间主要花在哪里？ | [Dynamo Router](evidence/router.json) 记录队列等待 516 ms，约占总耗时 96% | 客户端记录携带 Router 请求 ID |
| 进入引擎后为何又等了一轮？ | [准入事件](evidence/admission.json)中，已选请求数和本轮上限均为 1，命中 `prefill_max_requests` | W3C trace ID 贯穿适配器和 SGLang OTLP span |
| 哪轮执行了 Prefill？ | [MLX 执行记录](evidence/forward.json)显示 `metal:0`、`forward_iter=222` | 从[引擎根 span](evidence/engine_root.json)取 rid，匹配完成该轮的 batch 成员 |

Router 的计时从入队持续到出队检查和 overlap 刷新，按毫秒取整。Prefill 事件记录一次拒绝决定，不能用“总耗时减去 Router 等待”计算引擎排队时间。forward_iter 是这个 scheduler 进程的轮次。

## 这次实验如何构造

Apple Silicon Mac 上并发提交 32 条请求。ARM Linux 容器运行 Dynamo 1.6.0 的 Rust `KvRouter.best_worker`，通过 `Client.direct` 将请求发至选中实例的 TCP endpoint。演示适配器透传 traceparent，调用宿主机上的 SGLang MLX Engine。模型是本地生成的两层 FP16 Llama。每轮 Prefill 只准入一个请求；适配器收到完整生成响应后释放 Router 预订，以制造可观察的队列等待。这个实验验证单请求归因，未测生产吞吐或标准 OpenAI 网关路径。

公开样本保留这次实验随机生成的 trace ID、耗时、原因、计数和 forward 轮次。Router ID 和引擎 rid 按用途分别替换为别名。五份 JSON 是[按字段提取](live/extract.py)的样本，仅含一个请求。完整日志、OTLP 批次、输入内容、地址和进程号留在采集端。

## 在自己的 Mac 上复现采集

需要支持 Metal 的 Apple Silicon Mac、Git、uv、可运行 Linux ARM64 容器的 Apple Container，以及可供本实验使用的 4317 和 18888 端口。首次安装依赖和拉取镜像需要网络。从本 fork 的完整 Git 克隆运行：

```sh
bash examples/monitoring/dynamo_sglang_trace/live/run.sh
```

脚本创建独立临时目录，从已验证的 fork 提交 `587f068171` 提取 SGLang 源码，在副本中记录 MLX 完成的 Prefill batch；依赖版本列在 [Mac](live/requirements-mac.txt) 和 [Linux](live/requirements-linux.txt) 清单。脚本输出采集目录和该轮选中的 trace ID。每轮的 ID、等待时间和轮次都会变化。进入该目录后运行 `.venv/bin/python show_trace.py results <trace_id>` 可直接查询该轮原始数据。

相关上游贡献：[请求准入诊断 #50539](https://github.com/sgl-project/sglang/pull/50539) · [GPU 窗口分析 #50540](https://github.com/sgl-project/sglang/pull/50540)。这里的 forward 归属来自 MLX 调度器实际完成的 batch。
