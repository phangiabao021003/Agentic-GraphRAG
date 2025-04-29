from langchain_qdrant import FastEmbedSparse, QdrantVectorStore, RetrievalMode
from qdrant_client import QdrantClient, models
from graph.extract_graph import open_and_group_paragraphs
from qdrant_client.http.models import Distance, SparseVectorParams, VectorParams
from langchain.embeddings.ollama import OllamaEmbeddings
from langchain.text_splitter import RecursiveCharacterTextSplitter
from uuid import uuid4

sparse_embeddings = FastEmbedSparse(model_name="Qdrant/bm25")
embeddings = OllamaEmbeddings(model="")

# Create a Qdrant client for local storage
client = QdrantClient(path="C:/Users/bao.phangia/Downloads/Đồ án/vectordb")

pdf_path = "C:/Users/bao.phangia/Downloads/Đồ án/human-nutrition-text.pdf"
grouped_documents = open_and_group_paragraphs(pdf_path, start_page=45, paragraphs_per_doc=10)
text_splitter = RecursiveCharacterTextSplitter(    chunk_size=800,
                                                   chunk_overlap=150)
chunks = text_splitter.split_documents(grouped_documents)
# Create a collection with both dense and sparse vectors
client.create_collection(
    collection_name="Nutrition_hybrid",
    vectors_config={"dense": VectorParams(size=1024, distance=Distance.COSINE)},
    sparse_vectors_config={
        "sparse": SparseVectorParams(index=models.SparseIndexParams(on_disk=False))
    },
)

qdrant = QdrantVectorStore(
    client=client,
    collection_name="Nutrition_hybrid",
    embedding=embeddings,
    sparse_embedding=sparse_embeddings,
    retrieval_mode=RetrievalMode.HYBRID,
    vector_name="dense",
    sparse_vector_name="sparse",
)
uuids = [str(uuid4()) for _ in range(len(chunks))]
qdrant.add_documents(documents=chunks, ids=uuids)

