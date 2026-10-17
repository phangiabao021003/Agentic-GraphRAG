import logging

from qdrant_client.http.models import FieldCondition, Filter, MatchValue

from app.utils import rerank

logger = logging.getLogger(__name__)

FALLBACK_MESSAGE = "Không thể tìm thấy tài liệu liên quan"


def search(query, vectordb, reranker_model, reranker_tokenizer, doc_ids=None, top_k=3) -> str:
    try:
        filters = None
        if doc_ids:
            filters = Filter(
                must=[FieldCondition(key="metadata.doc_id", match=MatchValue(value=d)) for d in doc_ids]
            )

        vector_data = vectordb.similarity_search(query, k=7, filter=filters)
        if not vector_data:
            return FALLBACK_MESSAGE

        reranked_docs = rerank(query, vector_data, reranker_model, reranker_tokenizer, top_k=top_k)
        if not reranked_docs:
            return FALLBACK_MESSAGE

        cleaned = [
            f"{idx}. {doc.page_content.replace(chr(10), ' ')}"
            for idx, doc in enumerate(reranked_docs, start=1)
        ]
        return "\n".join(cleaned)
    except Exception:
        logger.exception("rag_search failed for query=%r", query)
        return FALLBACK_MESSAGE
