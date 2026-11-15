"""Local OTLP/gRPC receiver. Keep one raw protobuf per export."""

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from uuid import uuid4

import grpc
from opentelemetry.proto.collector.trace.v1 import trace_service_pb2 as msg
from opentelemetry.proto.collector.trace.v1 import trace_service_pb2_grpc as rpc


class Sink(rpc.TraceServiceServicer):
    def Export(self, request, context):
        Path("results", uuid4().hex + ".pb").write_bytes(request.SerializeToString())
        return msg.ExportTraceServiceResponse()


server = grpc.server(ThreadPoolExecutor(4))
rpc.add_TraceServiceServicer_to_server(Sink(), server)
assert server.add_insecure_port("127.0.0.1:4317")
server.start()
server.wait_for_termination()
