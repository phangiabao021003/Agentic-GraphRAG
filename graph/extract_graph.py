
import fitz  # PyMuPDF
from langchain.schema import Document
import pickle
from pathlib import Path
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_experimental.llms.ollama_functions import OllamaFunctions
from langchain_experimental.graph_transformers import LLMGraphTransformer

def extract_graph(chunks, graph_docs_pkl="graph_documents.pkl", failed_chunks_pkl="failed_chunks.pkl"):
    llm = OllamaFunctions(model="llama3.1", temperature=0.1, format="json")
    llm_transformer = LLMGraphTransformer(llm=llm)

    all_graph_docs = []
    failed_chunks = []

    for idx, chunk in enumerate(chunks):
        print(f"🔍 Đang xử lý chunk {idx+1}/{len(chunks)}...")
        try:
            graph_docs = llm_transformer.convert_to_graph_documents([chunk])
            all_graph_docs.extend(graph_docs)
        except Exception as e:
            failed_chunks.append(chunk)

    with open(graph_docs_pkl, "wb") as f:
        pickle.dump(all_graph_docs, f)

    if failed_chunks:
        with open(failed_chunks_pkl, "wb") as f:
            pickle.dump(failed_chunks, f)
    else:
        pass

    return all_graph_docs, failed_chunks


def  open_and_group_paragraphs(pdf_path: str, start_page=1, end_page=None, paragraphs_per_doc=10) -> list[Document]: 
    doc = fitz.open(pdf_path)
    full_text = ""

    for i, page in enumerate(doc):
        page_number = i + 1
        if page_number >= start_page and (end_page is None or page_number <= end_page):
            text = page.get_text()
            full_text += text + "\n"  # Đảm bảo vẫn giữ ngắt dòng

    # Tách đoạn (paragraph) theo \n\n
    paragraphs = [p.strip() for p in full_text.split("\n\n") if p.strip()]

    grouped_docs = []
    for i in range(0, len(paragraphs), paragraphs_per_doc):
        chunk_paragraphs = paragraphs[i:i + paragraphs_per_doc]
        chunk_text = "\n\n".join(chunk_paragraphs)

        metadata = {
            "source": pdf_path.split("/")[-1],
            "paragraph_range": f"{i+1}-{min(i+paragraphs_per_doc, len(paragraphs))}"
        }

        grouped_docs.append(Document(page_content=chunk_text, metadata=metadata))

    return grouped_docs

project_root = Path(__file__).resolve().parent.parent
graph_path = project_root / "graph_documents_nutrition.pkl"
pdf_path= project_root/ "human-nutrition-text.pdf"
if graph_path.exists():
    pass
else:
    grouped_documents = open_and_group_paragraphs(pdf_path, start_page=45, paragraphs_per_doc=10)
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=100
    )
    chunks = text_splitter.split_documents(grouped_documents)
    all_graph_docs, failed_chunks = extract_graph(chunks)
