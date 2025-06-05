import asyncio
from aiokafka import AIOKafkaConsumer
from services import parse, shutdown
import json
import grpc
from concurrent import futures
from cv_pb2_grpc import CVServiceServicer, add_CVServiceServicer_to_server
from cv_pb2 import CVResponse

class ParserService(CVServiceServicer):
    async def UploadCV(self, request_iterator, context):
        # Accumulate the incoming bytes from the stream.
        pdf_bytes = b""
        try:
            # Asynchronously iterate over each incoming CVRequest message.
            async for request in request_iterator:
                if context.cancelled():
                    await context.abort(grpc.StatusCode.CANCELLED, "Client cancelled the call")
                pdf_bytes += request.cv

            res = await parse(None, pdf_bytes)
            return CVResponse(response=res)
        except Exception as e:
            print(f"Error processing CV: {e}", flush=True)
            await context.abort(grpc.StatusCode.INTERNAL, f"Error processing CV: {e}")

    async def serve(self):
        server = grpc.aio.server(futures.ThreadPoolExecutor(max_workers=10))
        add_CVServiceServicer_to_server(ParserService(), server)
        server.add_insecure_port('0.0.0.0:50051')
        await server.start()
        await server.wait_for_termination()
        
async def consume():
    consumer = AIOKafkaConsumer(
        'cv_parsing',
        bootstrap_servers='kafka1:9092,kafka2:9092',
        group_id="parsing_group",
        enable_auto_commit=False,
        value_deserializer=lambda v: json.loads(v.decode('utf-8')) if v else None
    )
    await consumer.start()
    print("Consumer Started", flush=True)
    
    try:
        async for msg in consumer:
            try:
                if not msg.value:
                    print("Received empty message, skipping...", flush=True)
                    continue
                print(f"Consumed message: {msg.value}", flush=True)
                await parse(msg.value.get("id"))
                await consumer.commit()
            except Exception as e:
                print(f"Error processing message: {e}", flush=True)
    finally:
        await consumer.stop()
        await shutdown()

async def main():
    server_task = asyncio.create_task(ParserService().serve())
    consumer_task = asyncio.create_task(consume())
    await asyncio.gather(server_task, consumer_task)

asyncio.run(main())
