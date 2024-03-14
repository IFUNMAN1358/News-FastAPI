from redis.asyncio import StrictRedis

from app.config import Config

redis = StrictRedis(host=Config.redis_host,
                    port=Config.redis_port,
                    decode_responses=True,
                    protocol=3,
                    db=0)


async def get_redis():
    rds = await redis
    try:
        yield rds
    finally:
        await rds.aclose()
