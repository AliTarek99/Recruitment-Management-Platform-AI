import asyncio
from aiokafka import AIOKafkaConsumer
from Embeddings import main_function
import constants

async def consume():
    consumer = AIOKafkaConsumer(
        'cv_embedding_generation',
        'job_embedding_generation',
        'profile_embedding_generation',
        bootstrap_servers='localhost:9092',
        group_id="embedding_group",
        enable_auto_commit=False,
    )
    
    await consumer.start()
    try:
        async for msg in consumer:
            try:
                if msg.topic == 'cv_embedding_generation':
                    await main_function(msg.value.id, msg.value.userId, constants.CV_TYPE)
                elif msg.topic == 'job_embedding_generation':
                    await main_function(msg.value.id, None, constants.JOB_TYPE)
                elif msg.topic == 'profile_embedding_generation':
                    await main_function(None, msg.value.userId, constants.PROFILE_TYPE)
                await consumer.commit()
            except Exception as e:
                print(f"Error processing message: {e}")
    finally:
        await consumer.stop()

if __name__ == "__main__":
    asyncio.run(consume())