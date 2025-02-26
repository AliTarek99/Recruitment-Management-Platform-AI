import asyncio
from aiokafka import AIOKafkaConsumer
from Embeddings import main_function
import constants
import json

async def consume():
    print(0)
    consumer = AIOKafkaConsumer(
        'cv_embedding_generation',
        'job_embedding_generation',
        'profile_embedding_generation',
        bootstrap_servers='kafka1:9092,kafka2:9092',
        group_id="embedding_group",
        enable_auto_commit=False,
        value_deserializer=lambda v: json.loads(v.decode('utf-8'))
    )
    print(1)
    await consumer.start()
    print(2)
    try:
        async for msg in consumer:
            print(3)
            try:
                if msg.topic == 'cv_embedding_generation':
                    print(4)
                    await main_function(msg.value.get("id"), msg.value.get("userId"), constants.CV_TYPE)
                elif msg.topic == 'job_embedding_generation':
                    await main_function(msg.value.id, None, constants.JOB_TYPE)
                elif msg.topic == 'profile_embedding_generation':
                    await main_function(None, msg.value.userId, constants.PROFILE_TYPE)
                await consumer.commit()
            except Exception as e:
                print(f"Error processing message: {e}")
    finally:
        print(5)
        await consumer.stop()


print(-1)
asyncio.run(consume())