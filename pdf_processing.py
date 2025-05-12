# Requires !pip install PyMuPDF tqdm spacy
from langchain_qdrant import QdrantVectorStore, RetrievalMode
import re
from langchain.schema import Document
import fitz  # PyMuPDF
from tqdm.auto import tqdm
from pathlib import Path
import pandas as pd
from spacy.lang.en import English
from langchain_qdrant import QdrantVectorStore, RetrievalMode, FastEmbedSparse
from qdrant_client.http.models import Distance, SparseVectorParams, VectorParams
from uuid import uuid4
from qdrant_client.http.models import Filter
from qdrant_client import QdrantClient, models


def text_formatter(text: str) -> str:
    """Performs minor formatting on text."""
    cleaned_text = text.replace("\n", " ").strip()
    return cleaned_text

def open_and_read_pdf(pdf_path: str) -> list[dict]:
    """
    Opens a PDF file, reads its text content page by page, and collects statistics.
    """
    doc = fitz.open(pdf_path)
    pages_and_texts = []
    for page_number, page in tqdm(enumerate(doc)):
        text = page.get_text()
        text = text_formatter(text)
        pages_and_texts.append({
            "page_number": page_number - 41,
            "page_char_count": len(text),
            "page_word_count": len(text.split(" ")),
            "page_sentence_count_raw": len(text.split(". ")),
            "page_token_count": len(text) / 4,
            "text": text
        })
    return pages_and_texts

project_root = Path(__file__).resolve().parent  # chính là thư mục "Đồ án"
pdf_path = project_root / "human-nutrition-text.pdf"
pages_and_texts = open_and_read_pdf(pdf_path=pdf_path)

nlp = English()
nlp.add_pipe("sentencizer")

for item in tqdm(pages_and_texts):
    item["sentences"] = list(nlp(item["text"]).sents)
    item["sentences"] = [str(sentence) for sentence in item["sentences"]]
    item["page_sentence_count_spacy"] = len(item["sentences"])

df = pd.DataFrame(pages_and_texts)

num_sentence_chunk_size = 10

def split_list(input_list: list, slice_size: int) -> list[list[str]]:
    return [input_list[i:i + slice_size] for i in range(0, len(input_list), slice_size)]

for item in tqdm(pages_and_texts):
    item["sentence_chunks"] = split_list(input_list=item["sentences"], slice_size=num_sentence_chunk_size)
    item["num_chunks"] = len(item["sentence_chunks"])

df = pd.DataFrame(pages_and_texts)

pages_and_chunks = []
for item in tqdm(pages_and_texts):
    for sentence_chunk in item["sentence_chunks"]:
        chunk_dict = {}
        chunk_dict["page_number"] = item["page_number"]
        joined_sentence_chunk = "".join(sentence_chunk).replace("  ", " ").strip()
        joined_sentence_chunk = re.sub(r'\.([A-Z])', r'. \1', joined_sentence_chunk)
        chunk_dict["sentence_chunk"] = joined_sentence_chunk
        chunk_dict["chunk_char_count"] = len(joined_sentence_chunk)
        chunk_dict["chunk_word_count"] = len(joined_sentence_chunk.split(" "))
        chunk_dict["chunk_token_count"] = len(joined_sentence_chunk) / 4
        pages_and_chunks.append(chunk_dict)

len(pages_and_chunks)

df = pd.DataFrame(pages_and_chunks)

min_token_length = 30
pages_and_chunks_over_min_token_len = df[df["chunk_token_count"] > min_token_length].to_dict(orient="records")
documents = []
for chunk in pages_and_chunks_over_min_token_len:
    doc = Document(
        page_content=chunk["sentence_chunk"],
        metadata={
            "page_number": chunk["page_number"],
            "char_count": chunk["chunk_char_count"],
            "word_count": chunk["chunk_word_count"],
            "token_count": chunk["chunk_token_count"]
        }
    )
    documents.append(doc)
from langchain_community.embeddings import HuggingFaceEmbeddings

# Tạo embedding model từ Hugging Face
embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-mpnet-base-v2")
client = QdrantClient(path="./vectordb")
sparse_embeddings = FastEmbedSparse(model_name="Qdrant/bm25")

collections = client.get_collections().collections
collection_names = [c.name for c in collections]
if "Nutritionv5" not in collection_names:
    client.create_collection(
    collection_name="Nutritionv5",
    vectors_config={"dense": VectorParams(size=768, distance=Distance.COSINE)},
    sparse_vectors_config={
        "sparse": SparseVectorParams(index=models.SparseIndexParams(on_disk=False))
    },
)

    qdrant = QdrantVectorStore(
        client=client,
        collection_name="Nutritionv5",
        embedding=embeddings,
        sparse_embedding=sparse_embeddings,
        retrieval_mode=RetrievalMode.HYBRID,
        vector_name="dense",
        sparse_vector_name="sparse",)

    uuids = [str(uuid4()) for _ in range(len(documents))]
    qdrant.add_documents(documents=documents, ids=uuids)
else:   
    empty_filter = Filter(must=[])
    count_result = client.count(
        collection_name="Nutritionv5",
        count_filter=empty_filter,
    )
    print(f"Số vector trong 'Nutritionv5': {count_result.count}")