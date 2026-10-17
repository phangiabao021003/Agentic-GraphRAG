import logging

from mcp_server.utils import check_qdrant


class FakeQdrantOk:
    def get_collections(self):
        return {"collections": []}


class FakeQdrantFail:
    def get_collections(self):
        raise ConnectionError("boom")


def test_check_qdrant_returns_true_when_reachable():
    assert check_qdrant(FakeQdrantOk()) is True


def test_check_qdrant_returns_false_when_unreachable():
    assert check_qdrant(FakeQdrantFail()) is False


def test_check_qdrant_logs_exception_when_unreachable(caplog):
    with caplog.at_level(logging.ERROR):
        result = check_qdrant(FakeQdrantFail())
    assert result is False
    assert "Qdrant health check failed" in caplog.text
