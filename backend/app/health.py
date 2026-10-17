import logging

import asyncpg
import redis.asyncio as redis

logger = logging.getLogger(__name__)


async def check_postgres(pool: asyncpg.Pool) -> bool:
    try:
        await pool.fetchval("SELECT 1")
        return True
    except Exception:
        logger.exception("Postgres health check failed")
        return False


async def check_redis(client: redis.Redis) -> bool:
    try:
        return await client.ping()
    except Exception:
        logger.exception("Redis health check failed")
        return False
