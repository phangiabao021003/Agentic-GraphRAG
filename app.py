import streamlit as st
from typing import Optional
import os
import time
import json
from agents.agent_router import router_query
from graph.context_extractor import full_retriever
from prompt import enhancing_prompt, llm_prompt, schedule_prompt, process_json_ouput
from agents.agent_history import ContextAwareAgent
from qdrant_client import QdrantClient
from langchain.embeddings.ollama import OllamaEmbeddings
from langchain_qdrant import FastEmbedSparse, QdrantVectorStore, RetrievalMode
from langchain_community.embeddings import HuggingFaceEmbeddings
from calendar_tool.agent_calendar import GoogleCalendar
from openai import OpenAI
from dotenv import load_dotenv
from graph.graphdb_connection import GraphDBConnection
from google import genai

from langchain.document_loaders import PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from pdf_processing import process_pdf_to_documents, create_vectordb
from uuid import uuid4
from qdrant_client.http.models import VectorParams, Distance, SparseVectorParams
from qdrant_client.http.models import CollectionInfo

load_dotenv()

# === Khởi tạo các đối tượng và cấu hình ===
gemini = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
client = OpenAI(base_url='http://localhost:11434/v1', api_key='dolphin-llama3')

chat_history=[]
calendar_agent = GoogleCalendar()
his_agent=ContextAwareAgent(client=client,chat_history=chat_history,max_context_tokens=4000)

embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-mpnet-base-v2")
sparse_embeddings = FastEmbedSparse(model_name="Qdrant/bm25")
vectordb = QdrantClient(path="./vectordb")
qdrant = QdrantVectorStore(
    client=vectordb,
    collection_name="Nutritionv5",
    embedding=embeddings,
    sparse_embedding=sparse_embeddings,
    retrieval_mode=RetrievalMode.HYBRID,
    vector_name="dense",
    sparse_vector_name="sparse"
)

# === Kết nối Neo4j ===
driver = GraphDBConnection(
    uri="bolt://localhost:7687",
    username="neo4j",
    password=os.environ.get("NEO4J_PASSWORD"),
    database="graduation"
)
graph = driver.connect_to_graph()
driver.setup_index()
driver.close()

# === Các hàm xử lý ===
def stream(query: str, temperature: Optional[float] = 0.5):
    response = client.chat.completions.create(
        model='llama3.2',
        messages=[{"role": "user", "content": query}],
        max_tokens=2048,
        stream=True,
        temperature=temperature,
    )
    collected_message = ""
    for chunk in response:
        if chunk.choices:
            content = chunk.choices[0].delta.content or ""
            collected_message += content
    return collected_message

def ask(query: str, temperature: Optional[float] = 0.5):
    response = client.chat.completions.create(
        model='llama3.2',
        messages=[{"role": "user", "content": query}],
        max_tokens=2048,
        temperature=temperature,
    )
    return response.choices[0].message.content

def handle_llm(query, new_query):
    new_prompt = llm_prompt(new_query, context=None)
    return stream(new_prompt, 0.5)

def handle_rag(query, new_query):
    context = full_retriever(graph, qdrant, query)
    new_prompt = enhancing_prompt(new_query, context)
    return stream(new_prompt, 0.1)

def handle_calendar(new_query):
    new_prompt = schedule_prompt(new_query)
    response = gemini.models.generate_content(
        model="gemini-2.0-flash",
        contents=new_prompt,
        config={'response_mime_type': 'application/json'}
    )
    events = json.loads(response.text)
    json_explain_prompt = process_json_ouput(events)
    answer = ask(json_explain_prompt, 0.1)
    for event in events:
        operation = event['operation']
        if operation in {"CREATE", "UPDATE", "DELETE"}:
            calendar_agent.insert_event(json_input=event)
        elif operation == "READ":
            calendar_agent.list_event(json_input=event)
    return answer

def embed_file(uploaded_file):
    file_path = f"./tmp/{uploaded_file.name}"
    with open(file_path, "wb") as f:
        f.write(uploaded_file.read())
    collection_name = os.path.splitext(os.path.basename(file_path))[0]

    # Process PDF using the same logic as pdf_processing.py
    documents = process_pdf_to_documents(file_path)
    # Create collection if it doesn't exist
    create_vectordb(client=vectordb, 
                    collection_name=collection_name,
                    documents=documents, 
                    embeddings=embeddings,
                    sparse_embeddings=sparse_embeddings)
    

# === Giao diện Streamlit ===
st.set_page_config(page_title="Agent RAG + Calendar", layout="wide")
st.title("🧠 Agent Chatbot: RAG, LLM & Calendar")

with st.sidebar:
    st.header("📎 Upload documents")
    uploaded_file = st.file_uploader("Upload PDF", type=["pdf"])
    if uploaded_file:
        st.success(embed_file(uploaded_file))

st.subheader("💬 Gửi câu hỏi")
user_query = st.text_input("Nhập câu hỏi của bạn...")
route_option = st.radio("Chọn phương thức xử lý", options=["Auto", "llm", "rag", "calendar"])

if st.button("Gửi câu hỏi"):
    if user_query:
        new_query = his_agent.generate_reply(user_query)
        his_agent.add_to_history("user", new_query)

        if route_option == "Auto":
            route = router_query(new_query)
        else:
            route = route_option

        if route == "llm":
            output = handle_llm(user_query, new_query)
        elif route == "rag":
            output = handle_rag(user_query, new_query)
        elif route == "calendar":
            output = handle_calendar(new_query)
        else:
            output = "Không xác định route phù hợp."

        his_agent.add_to_history("assistant", output)
        st.markdown("### ✅ Phản hồi:")
        st.write(output)
    else:
        st.warning("Vui lòng nhập câu hỏi.")

