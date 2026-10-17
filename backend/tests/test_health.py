import logging

from app.health import check_postgres, check_redis


class FakePoolOk:
    async def fetchval(self, query):
        return 1


class FakePoolFail:
    async def fetchval(self, query):
        raise ConnectionError("boom")


class FakeRedisOk:
    async def ping(self):
        return True


class FakeRedisFail:
    async def ping(self):
        raise ConnectionError("boom")


async def test_check_postgres_returns_true_when_reachable():
    assert await check_postgres(FakePoolOk()) is True


async def test_check_postgres_returns_false_when_unreachable():
    assert await check_postgres(FakePoolFail()) is False


async def test_check_redis_returns_true_when_reachable():
    assert await check_redis(FakeRedisOk()) is True


async def test_check_redis_returns_false_when_unreachable():
    assert await check_redis(FakeRedisFail()) is False


async def test_check_postgres_logs_exception_when_unreachable(caplog):
    with caplog.at_level(logging.ERROR):
        result = await check_postgres(FakePoolFail())
    assert result is False
    assert "Postgres health check failed" in caplog.text


async def test_check_redis_logs_exception_when_unreachable(caplog):
    with caplog.at_level(logging.ERROR):
        result = await check_redis(FakeRedisFail())
    assert result is False
    assert "Redis health check failed" in caplog.text
