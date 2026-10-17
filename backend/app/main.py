from contextlib import asynccontextmanager

import asyncpg
import redis.asyncio as redis
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.auth.routes import router as auth_router
from app.api.chat import router as chat_router
from app.api.conversations import router as conversation_router
from app.api.documents import router as document_router
from app.config import settings
from app.health import check_postgres, check_redis


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.pg_pool = await asyncpg.create_pool(settings.database_url)
    app.state.redis_client = redis.from_url(settings.redis_url)
    yield
    await app.state.pg_pool.close()
    await app.state.redis_client.aclose()


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(chat_router)
app.include_router(conversation_router)
app.include_router(document_router)


@app.get("/health")
async def health():
    postgres_ok = await check_postgres(app.state.pg_pool)
    redis_ok = await check_redis(app.state.redis_client)
    return {
        "status": "ok" if postgres_ok and redis_ok else "degraded",
        "postgres": postgres_ok,
        "redis": redis_ok,
    }
