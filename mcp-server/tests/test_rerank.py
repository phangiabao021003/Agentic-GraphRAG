from types import SimpleNamespace

import torch

from mcp_server.utils import rerank


class FakeDoc:
    def __init__(self, page_content):
        self.page_content = page_content


class FakeTokenizer:
    def __call__(self, pairs, **kwargs):
        return {"input_ids": torch.zeros((len(pairs), 1), dtype=torch.long)}


class FakeModel:
    def __init__(self, scores):
        self._scores = scores

    def __call__(self, **kwargs):
        return SimpleNamespace(logits=torch.tensor(self._scores).unsqueeze(1))


def test_rerank_orders_by_score_descending():
    docs = [FakeDoc("low"), FakeDoc("high"), FakeDoc("medium")]
    model = FakeModel([0.1, 0.9, 0.5])
    result = rerank("query", docs, model, FakeTokenizer(), top_k=3)
    assert [doc.page_content for doc in result] == ["high", "medium", "low"]


def test_rerank_respects_top_k():
    docs = [FakeDoc("low"), FakeDoc("high"), FakeDoc("medium")]
    model = FakeModel([0.1, 0.9, 0.5])
    result = rerank("query", docs, model, FakeTokenizer(), top_k=2)
    assert len(result) == 2
    assert [doc.page_content for doc in result] == ["high", "medium"]
