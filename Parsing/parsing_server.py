import asyncio
from aiokafka import AIOKafkaConsumer
from services import parse
import json
import grpc
from concurrent import futures
from cv_pb2_grpc import CVServiceServicer, add_CVServiceServicer_to_server
from cv_pb2 import CVResponse

class ParserService(CVServiceServicer):
    async def ParsePDF(self, request, context):
        try:
            pdf_bytes = request.cv
            # Call the parser with the PDF bytes
            res = json.dumps(parse(pdf_bytes))
            return CVResponse(res)
        except Exception as e:
            return CVResponse(status=f"Error: {e}")
        
    async def serve(self):
        server = grpc.aio.server(futures.ThreadPoolExecutor(max_workers=10))
        add_CVServiceServicer_to_server(ParserService(), server)
        server.add_insecure_port('[::]:50051')
        await server.start()
        await server.wait_for_termination()
        
async def consume():
    consumer = AIOKafkaConsumer(
        'cv_parsing',
        bootstrap_servers='kafka1:9092,kafka2:9092',
        group_id="parsing_group",
        enable_auto_commit=False,
        value_deserializer=lambda v: json.loads(v.decode('utf-8'))
    )
    print("Starting consumer", flush=True)
    await consumer.start()
    try:
        async for msg in consumer:
            try:
                print(f"Consumed message: {msg.value}", flush=True)
                await parse(msg.value.get("id"))
                await consumer.commit()
            except Exception as e:
                print(f"Error processing message: {e}", flush=True)
    finally:
        await consumer.stop()

async def main():
    server_task = asyncio.create_task(ParserService().serve())
    consumer_task = asyncio.create_task(consume())
    await asyncio.gather(server_task, consumer_task)

asyncio.run(main())
