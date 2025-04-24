from graph.extract_graph import open_and_group_paragraphs
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.embeddings.ollama import OllamaEmbeddings
from langchain_qdrant import QdrantVectorStore, RetrievalMode
from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, VectorParams
from uuid import uuid4
from qdrant_client.http.models import Filter


embeddings = OllamaEmbeddings(model="bge-m3")
# Create a Qdrant client for local storage
client = QdrantClient(path="./vectordb")
pdf_path = "C:/Users/bao.phangia/Downloads/Đồ án/human-nutrition-text.pdf"
grouped_documents = open_and_group_paragraphs(pdf_path, start_page=46, end_page=1190, paragraphs_per_doc=10)
text_splitter = RecursiveCharacterTextSplitter(chunk_size=800,chunk_overlap=150)
chunks = text_splitter.split_documents(grouped_documents)
print("chunks\n",len(chunks))
collections = client.get_collections().collections
collection_names = [c.name for c in collections]
if "Nutritionv3" not in collection_names:

    client.create_collection(
        collection_name="Nutritionv3",
        vectors_config=VectorParams(size=1024, distance=Distance.COSINE))
    qdrant = QdrantVectorStore(
        client=client,
        collection_name="Nutritionv3",
        embedding=embeddings,
        retrieval_mode=RetrievalMode.DENSE
    )
    uuids = [str(uuid4()) for _ in range(len(chunks))]
    qdrant.add_documents(documents=chunks, ids=uuids)
else:   
    empty_filter = Filter(must=[])
    count_result = client.count(
        collection_name="Nutritionv3",
        count_filter=empty_filter,
    )
    print(f"Số vector trong 'Nutritionv2': {count_result.count}")