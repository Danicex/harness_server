import redis.asyncio as redis
import os
from dotenv import load_dotenv

load_dotenv()

    
REDIS_PORT = os.getenv("REDIS_PORT")
REDIS_PASSWORD = os.getenv("REDIS_PORT")

redis_client = redis.Redis(
    host='localhost',
    port=REDIS_PORT,
    password=REDIS_PASSWORD,
    db=int(0),
    decode_responses=True
)
