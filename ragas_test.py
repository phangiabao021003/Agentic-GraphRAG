import os
from llama_index.readers.file.docs import DocxReader, PDFReader
from llama_index.readers.file.markdown import MarkdownReader
from llama_index.readers.file.flat import FlatReader
from ragas.testset import TestsetGenerator
from langchain_openai import ChatOpenAI
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain.schema import Document as LCDocument

def load_documents_from_directory(directory: str):
    documents = []

    for filename in os.listdir(directory):
        filepath = os.path.join(directory, filename)

        if filename.endswith(".pdf"):
            reader = PDFReader()
            docs = reader.load_data(filepath)
        elif filename.endswith(".docx"):
            reader = DocxReader()
            docs = reader.load_data(filepath)
        elif filename.endswith(".md"):
            reader = MarkdownReader()
            docs = reader.load_data(filepath)
        elif filename.endswith(".txt"):
            reader = FlatReader()
            docs = reader.load_data(filepath)
        else:
            print(f"❌ Unsupported file: {filename}")
            continue

        documents.extend(docs)
    
    return documents

# Load documents
documents = load_documents_from_directory("./data")

# Chuyển đổi sang LCDocument chuẩn cho Ragas
ragas_docs = [
    LCDocument(
        page_content=doc.get_content() if hasattr(doc, "get_content") else getattr(doc, "text", ""),
        metadata=getattr(doc, "metadata", {})
    )
    for doc in documents
]

# Khởi tạo các LLM và embeddings
generator_llm = ChatOpenAI(
    model="llama3.2",
    base_url="http://localhost:11434/v1",
    api_key="ollama"
)
critic_llm = ChatOpenAI(
    model="llama3.2",
    base_url="http://localhost:11434/v1",
    api_key="ollama"
)
embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-mpnet-base-v2")

# Khởi tạo TestsetGenerator
generator = TestsetGenerator.from_langchain(
    generator_llm,
    critic_llm,
    embeddings
)

# Generate testset
testset = generator.generate_with_langchain_docs(
    ragas_docs,
    testset_size=100
)

print(testset.to_pandas())
