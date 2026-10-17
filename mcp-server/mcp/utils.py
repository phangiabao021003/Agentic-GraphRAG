"""Standalone, model-free helper functions (merged from health.py, rerank.py,
pdf_chunking.py). This module must stay importable WITHOUT loading any ML model —
that is what keeps the unit tests fast."""
import logging
import re
from pathlib import Path

import fitz
import pandas as pd
import torch
from langchain_core.documents import Document
from qdrant_client import QdrantClient
from spacy.lang.en import English

logger = logging.getLogger(__name__)


def check_qdrant(client: QdrantClient) -> bool:
    try:
        client.get_collections()
        return True
    except Exception:
        logger.exception("Qdrant health check failed")
        return False


def rerank(query, docs, model, tokenizer, top_k=4):
    pairs = [(query, doc.page_content) for doc in docs]
    with torch.no_grad():
        inputs = tokenizer(pairs, padding=True, truncation=True, return_tensors="pt", max_length=512)
        scores = model(**inputs, return_dict=True).logits.view(-1,).float()

    scored_docs = list(zip(docs, scores.tolist()))
    reranked = sorted(scored_docs, key=lambda x: x[1], reverse=True)
    return [doc for doc, score in reranked[:top_k]]


def process_pdf_to_documents(
    pdf_path: str, num_sentence_chunk_size: int = 10, min_token_length: int = 30
) -> list[Document]:
    def text_formatter(text: str) -> str:
        return text.replace("\n", " ").strip()

    def split_list(input_list: list, slice_size: int) -> list[list[str]]:
        return [input_list[i : i + slice_size] for i in range(0, len(input_list), slice_size)]

    doc = fitz.open(pdf_path)
    pages_and_texts = []
    for page_number, page in enumerate(doc):
        pages_and_texts.append({"page_number": page_number, "text": text_formatter(page.get_text())})

    nlp = English()
    nlp.add_pipe("sentencizer")
    for item in pages_and_texts:
        item["sentences"] = [str(sent) for sent in nlp(item["text"]).sents]

    for item in pages_and_texts:
        item["sentence_chunks"] = split_list(item["sentences"], num_sentence_chunk_size)

    pages_and_chunks = []
    for item in pages_and_texts:
        for sentence_chunk in item["sentence_chunks"]:
            joined_chunk = "".join(sentence_chunk).replace("  ", " ").strip()
            joined_chunk = re.sub(r"\.([A-Z])", r". \1", joined_chunk)
            pages_and_chunks.append(
                {
                    "page_number": item["page_number"],
                    "sentence_chunk": joined_chunk,
                    "chunk_char_count": len(joined_chunk),
                    "chunk_word_count": len(joined_chunk.split(" ")),
                    "chunk_token_count": len(joined_chunk) / 4,
                }
            )

    df_chunks = pd.DataFrame(pages_and_chunks)
    filtered_chunks = df_chunks[df_chunks["chunk_token_count"] > min_token_length].to_dict(orient="records")

    doc_id = Path(pdf_path).stem
    documents = []
    for chunk in filtered_chunks:
        documents.append(
            Document(
                page_content=chunk["sentence_chunk"],
                metadata={
                    "doc_id": doc_id,
                    "page_number": chunk["page_number"],
                    "char_count": chunk["chunk_char_count"],
                    "word_count": chunk["chunk_word_count"],
                    "token_count": chunk["chunk_token_count"],
                },
            )
        )
    return documents
