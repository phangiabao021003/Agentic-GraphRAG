import logging

from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_qdrant import FastEmbedSparse, QdrantVectorStore, RetrievalMode
from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, SparseVectorParams, VectorParams, models
from transformers import AutoModelForSequenceClassification, AutoTokenizer

from mcp_server.config import settings

logger = logging.getLogger(__name__)

COLLECTION_NAME = "human-nutrition.pdf"

logger.info("Loading dense embedding model (BAAI/bge-m3)...")
embeddings = HuggingFaceEmbeddings(model_name="BAAI/bge-m3")

logger.info("Loading sparse embedding model (Qdrant/bm25)...")
sparse_embeddings = FastEmbedSparse(model_name="Qdrant/bm25")

logger.info("Loading reranker model (BAAI/bge-reranker-v2-m3)...")
reranker_tokenizer = AutoTokenizer.from_pretrained("BAAI/bge-reranker-v2-m3")
reranker_model = AutoModelForSequenceClassification.from_pretrained("BAAI/bge-reranker-v2-m3")
reranker_model.eval()

qdrant_client = QdrantClient(url=settings.qdrant_url)

existing_collections = [c.name for c in qdrant_client.get_collections().collections]
if COLLECTION_NAME not in existing_collections:
    logger.info("Creating Qdrant collection %r...", COLLECTION_NAME)
    qdrant_client.create_collection(
        collection_name=COLLECTION_NAME,
        vectors_config={"dense": VectorParams(size=1024, distance=Distance.COSINE)},
        sparse_vectors_config={"sparse": SparseVectorParams(index=models.SparseIndexParams(on_disk=False))},
    )

vectordb = QdrantVectorStore(
    client=qdrant_client,
    collection_name=COLLECTION_NAME,
    embedding=embeddings,
    sparse_embedding=sparse_embeddings,
    retrieval_mode=RetrievalMode.HYBRID,
    vector_name="dense",
    sparse_vector_name="sparse",
)

logger.info("All RAG models loaded.")
