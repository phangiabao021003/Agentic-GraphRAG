from pathlib import Path

from app.utils import process_pdf_to_documents

FIXTURE_PDF = Path(__file__).resolve().parent / "fixtures" / "sample.pdf"


def test_process_pdf_to_documents_returns_chunks_with_doc_id():
    documents = process_pdf_to_documents(str(FIXTURE_PDF))
    assert len(documents) > 0
    assert all(doc.metadata["doc_id"] == "sample" for doc in documents)
    assert all(doc.page_content.strip() for doc in documents)


def test_process_pdf_to_documents_respects_min_token_length():
    documents = process_pdf_to_documents(str(FIXTURE_PDF), min_token_length=30)
    assert all(doc.metadata["token_count"] > 30 for doc in documents)
