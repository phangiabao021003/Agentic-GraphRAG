# Requires !pip install PyMuPDF tqdm spacy
from langchain_qdrant import QdrantVectorStore, RetrievalMode
import re
from typing import Optional
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
from langchain_community.embeddings import HuggingFaceEmbeddings

def get_all_doc_ids_from_collection(qdrant_client:QdrantClient,collection_name: str, limit: int = 100) -> list:
    
    all_doc_ids = set()
    scroll_offset = None

    while True:
        # Lấy dữ liệu từ Qdrant
        response = qdrant_client.scroll(
            collection_name=collection_name,
            scroll_filter=None,  # Không sử dụng filter
            limit=limit,  # Số lượng điểm lấy mỗi lần
            offset=scroll_offset,  # Vị trí bắt đầu scroll
            with_payload=True,  # Bao gồm payload để lấy doc_id
            with_vectors=False  # Không lấy vectors
        )
        
        # Duyệt qua các điểm (points) trả về
        points = response[0]
        if not points:
            break  # Nếu không còn dữ liệu thì thoát vòng lặp

        # Lấy doc_id từ metadata trong payload
        for point in points:
            metadata = point.payload.get("metadata", {})  # Lấy metadata từ payload
            doc_id = metadata.get("doc_id")  # Lấy doc_id từ metadata
            if doc_id:
                all_doc_ids.add(doc_id)  # Thêm doc_id vào set (để tránh trùng lặp)

        # Lấy scroll_offset để tiếp tục phân trang
        scroll_offset = response[1]
        if scroll_offset is None:
            break  # Nếu không còn dữ liệu thì thoát

    return sorted(all_doc_ids)

def process_pdf_to_documents(pdf_path: str, num_sentence_chunk_size: int = 10, min_token_length: int = 30):
    def text_formatter(text: str) -> str:
        """Performs minor formatting on text."""
        return text.replace("\n", " ").strip()

    def split_list(input_list: list, slice_size: int) -> list[list[str]]:
        return [input_list[i:i + slice_size] for i in range(0, len(input_list), slice_size)]

    # Đọc nội dung PDF từng trang
    doc = fitz.open(pdf_path)
    pages_and_texts = []

    for page_number, page in tqdm(enumerate(doc), desc="Reading PDF"):
        text = page.get_text()
        text = text_formatter(text)
        pages_and_texts.append({
            "page_number": page_number,  # Offset page number (tuỳ mục đích)
            "page_char_count": len(text),
            "page_word_count": len(text.split(" ")),
            "page_sentence_count_raw": len(text.split(". ")),
            "page_token_count": len(text) / 4,
            "text": text
        })

    # Tách câu bằng spaCy
    nlp = English()
    nlp.add_pipe("sentencizer")
    for item in tqdm(pages_and_texts, desc="Splitting Sentences"):
        item["sentences"] = [str(sent) for sent in nlp(item["text"]).sents]
        item["page_sentence_count_spacy"] = len(item["sentences"])

    # Chia nhỏ đoạn văn thành các cụm câu
    for item in tqdm(pages_and_texts, desc="Chunking Sentences"):
        item["sentence_chunks"] = split_list(item["sentences"], num_sentence_chunk_size)
        item["num_chunks"] = len(item["sentence_chunks"])

    # Tạo các chunk từ cụm câu
    pages_and_chunks = []
    for item in tqdm(pages_and_texts, desc="Formatting Chunks"):
        for sentence_chunk in item["sentence_chunks"]:
            joined_chunk = "".join(sentence_chunk).replace("  ", " ").strip()
            joined_chunk = re.sub(r'\.([A-Z])', r'. \1', joined_chunk)
            pages_and_chunks.append({
                "page_number": item["page_number"],
                "sentence_chunk": joined_chunk,
                "chunk_char_count": len(joined_chunk),
                "chunk_word_count": len(joined_chunk.split(" ")),
                "chunk_token_count": len(joined_chunk) / 4
            })

    # Lọc chunk có độ dài tối thiểu
    df_chunks = pd.DataFrame(pages_and_chunks)
    filtered_chunks = df_chunks[df_chunks["chunk_token_count"] > min_token_length].to_dict(orient="records")

    # Tạo danh sách Document
    documents = []
    doc_id= Path(pdf_path).stem
    for chunk in filtered_chunks:
        documents.append(Document(
            page_content=chunk["sentence_chunk"],
            metadata={
                "doc_id": doc_id,
                "page_number": chunk["page_number"],
                "char_count": chunk["chunk_char_count"],
                "word_count": chunk["chunk_word_count"],
                "token_count": chunk["chunk_token_count"]
            }
        ))

    return documents

def create_vectordb(client:QdrantClient,
                    collection_name: Optional[str],
                    documents: list[Document],
                    existed_docs:set,
                    embeddings: HuggingFaceEmbeddings,
                    sparse_embeddings: FastEmbedSparse):
    if collection_name:
        collections = client.get_collections().collections
        collection_names = [c.name for c in collections]
        if "human-nutrition-text.pdf" not in collection_names:
            client.create_collection(
            collection_name="human-nutrition-text.pdf",
            vectors_config={"dense": VectorParams(size=768, distance=Distance.COSINE)},
            sparse_vectors_config={
                "sparse": SparseVectorParams(index=models.SparseIndexParams(on_disk=False))
            },
        )
    else:
        collection_name = "human-nutrition-text.pdf"

    doc_id = next(iter(set(doc.metadata["doc_id"] for doc in documents)))

    existing = doc_id in existed_docs
    if existing:
        output=f"❌ Documenet '{doc_id}' existed in vectordb."
        return output
    else:
        qdrant = QdrantVectorStore(
            client=client,
            collection_name=collection_name,
            embedding=embeddings,
            sparse_embedding=sparse_embeddings,
            retrieval_mode=RetrievalMode.HYBRID,
            vector_name="dense",
            sparse_vector_name="sparse",)

        uuids = [str(uuid4()) for _ in range(len(documents))]
        qdrant.add_documents(documents=documents, ids=uuids)

# Tạo embedding model từ Hugging Face
embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-mpnet-base-v2")
client = QdrantClient(host="localhost", port=6333)
sparse_embeddings = FastEmbedSparse(model_name="Qdrant/bm25")
collections = client.get_collections().collections
collection_names = [c.name for c in collections]
if "human-nutrition-text.pdf" not in collection_names:
            client.create_collection( collection_name="human-nutrition-text.pdf",
                                      vectors_config={"dense": VectorParams(size=768, distance=Distance.COSINE)},
                                      sparse_vectors_config={"sparse": SparseVectorParams(index=models.SparseIndexParams(on_disk=False))})
existed_docs = get_all_doc_ids_from_collection(
            qdrant_client=QdrantClient(host="localhost", port=6333),
            collection_name="human-nutrition-text.pdf",
            limit=10
        )
project_root = Path(__file__).resolve().parent
pdf_path = project_root / "human-nutrition-text.pdf"
documents = process_pdf_to_documents(str(pdf_path))
collection_name = pdf_path.name

create_vectordb(client=client, collection_name=None, documents=documents, existed_docs=existed_docs, embeddings=embeddings, sparse_embeddings=sparse_embeddings)