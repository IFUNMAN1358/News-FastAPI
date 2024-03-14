from redis.asyncio import StrictRedis


async def hsetex(redis: StrictRedis,
                 name: str,
                 mapping: dict,
                 time: int):
    await redis.hset(name=name,
                     mapping=mapping)
    await redis.expire(name=name, time=time)
