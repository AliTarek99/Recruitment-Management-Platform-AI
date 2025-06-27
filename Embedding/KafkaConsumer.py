import asyncio
from aiokafka import AIOKafkaConsumer
from Embeddings import main_function
import constants
import json

async def consume():
    
    consumer = AIOKafkaConsumer(
        'cv_embedding_generation',
        'job_embedding_generation',
        'profile_embedding_generation',
        bootstrap_servers='kafka1:9092,kafka2:9092',
        group_id="embedding_group",
        enable_auto_commit= True,
        value_deserializer=lambda v: json.loads(v.decode('utf-8')),
        request_timeout_ms=60000,
        session_timeout_ms=60000,
        auto_offset_reset='earliest',
    )
    
    await consumer.start()
    try:
        async for msg in consumer:
            try:
                if msg.topic == 'cv_embedding_generation':
                    await main_function(msg.value.get("id"), msg.value.get("userId"), constants.CV_TYPE)
                elif msg.topic == 'job_embedding_generation':
                    await main_function(msg.value.get("jobId"), None, constants.JOB_TYPE)
                elif msg.topic == 'profile_embedding_generation':
                    await main_function(None, msg.value.get("userId"), constants.PROFILE_TYPE)
            except Exception as e:
                print(f"Error processing message: {e}", flush=True)
    finally:
        await consumer.stop()



asyncio.run(consume())