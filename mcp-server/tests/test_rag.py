from types import SimpleNamespace

import torch

from mcp_server.tools.rag import FALLBACK_MESSAGE, search


class FakeDoc:
    def __init__(self, page_content):
        self.page_content = page_content


class FakeTokenizer:
    def __call__(self, pairs, **kwargs):
        return {"input_ids": torch.zeros((len(pairs), 1), dtype=torch.long)}


class FakeModel:
    def __call__(self, **kwargs):
        n = kwargs["input_ids"].shape[0]
        return SimpleNamespace(logits=torch.ones((n, 1)))


class FakeVectorDBEmpty:
    def similarity_search(self, query, k, filter):
        return []


class FakeVectorDBWithResults:
    def __init__(self, docs):
        self._docs = docs

    def similarity_search(self, query, k, filter):
        return self._docs


class FakeVectorDBRaises:
    def similarity_search(self, query, k, filter):
        raise ConnectionError("qdrant down")


def test_search_returns_fallback_when_no_results():
    result = search("query", FakeVectorDBEmpty(), FakeModel(), FakeTokenizer())
    assert result == FALLBACK_MESSAGE


def test_search_returns_fallback_when_vectordb_raises():
    result = search("query", FakeVectorDBRaises(), FakeModel(), FakeTokenizer())
    assert result == FALLBACK_MESSAGE


def test_search_returns_numbered_context_on_success():
    docs = [FakeDoc("first passage"), FakeDoc("second passage")]
    result = search("query", FakeVectorDBWithResults(docs), FakeModel(), FakeTokenizer(), top_k=2)
    assert result == "1. first passage\n2. second passage"


def test_search_applies_doc_ids_filter_without_error():
    docs = [FakeDoc("only passage")]
    result = search(
        "query", FakeVectorDBWithResults(docs), FakeModel(), FakeTokenizer(), doc_ids=["some-doc"], top_k=1
    )
    assert result == "1. only passage"
