import logging
from pathlib import Path
from uuid import uuid4

from mcp_server.models import COLLECTION_NAME, qdrant_client, vectordb
from mcp_server.utils import process_pdf_to_documents

logger = logging.getLogger(__name__)


def get_all_doc_ids(limit: int = 100) -> list[str]:
    all_doc_ids: set[str] = set()
    scroll_offset = None
    while True:
        points, scroll_offset = qdrant_client.scroll(
            collection_name=COLLECTION_NAME,
            limit=limit,
            offset=scroll_offset,
            with_payload=True,
            with_vectors=False,
        )
        if not points:
            break
        for point in points:
            doc_id = point.payload.get("metadata", {}).get("doc_id")
            if doc_id:
                all_doc_ids.add(doc_id)
        if scroll_offset is None:
            break
    return sorted(all_doc_ids)


def ingest_pdf(pdf_path: str) -> dict:
    doc_id = Path(pdf_path).stem
    try:
        if doc_id in get_all_doc_ids():
            return {"status": "already_exists", "message": f"Document '{doc_id}' already exists."}

        documents = process_pdf_to_documents(pdf_path)
        uuids = [str(uuid4()) for _ in documents]
        vectordb.add_documents(documents=documents, ids=uuids)
        return {"status": "success", "message": f"Ingested '{doc_id}' ({len(documents)} chunks)."}
    except Exception:
        logger.exception("Failed to ingest PDF %s", pdf_path)
        return {"status": "error", "message": f"Failed to ingest '{doc_id}'."}
