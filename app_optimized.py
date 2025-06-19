import os
os.environ["STREAMLIT_SERVER_ENABLE_FILE_WATCHER"] = "false"
import streamlit as st
import threading
from typing import Optional
import os
import json
# from search_agent.react import ReActPipeline
from agents.agent_router import router_query
from graph.context_extractor import full_retriever, chrome, web_searching
from config import enhancing_prompt, llm_prompt, schedule_prompt, process_json_ouput
from agents.agent_history import ContextAwareAgent
from qdrant_client import QdrantClient
from langchain_qdrant import FastEmbedSparse, QdrantVectorStore, RetrievalMode
from langchain_community.embeddings import HuggingFaceEmbeddings
from calendar_tool.agent_calendar import GoogleCalendar
from openai import OpenAI
from dotenv import load_dotenv
from graph.graphdb_connection import GraphDBConnection
from google import genai
from pdf_processing import process_pdf_to_documents, create_vectordb
import time
from queue import Queue
from search_agent.google import seach_web
from search_agent.web_reader import read_web


load_dotenv()
api_key = os.getenv("SERPAPI_API_KEY")

# Khởi tạo session state nếu chưa tồn tại
if 'initialized' not in st.session_state:
    st.session_state.initialized = False

# Hàm khởi tạo các kết nối và đối tượng
def initialize_connections():
    if not st.session_state.initialized:
        st.session_state.gemini = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
        st.session_state.client = OpenAI(
            base_url='http://localhost:11434/v1',
            api_key='dolphin-llama3'
        )
        st.session_state.embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-mpnet-base-v2")
        st.session_state.sparse_embeddings = FastEmbedSparse(model_name="Qdrant/bm25")
        st.session_state.calendar_agent = GoogleCalendar()
        st.session_state.history_chat = []
        st.session_state.his_agent = ContextAwareAgent(client=st.session_state.client, max_context_tokens=4000)
        
        # Khởi tạo Qdrant
        st.session_state.qdrant = QdrantClient(host="localhost", port=6333)
        st.session_state.vectordb = QdrantVectorStore(
            client=st.session_state.qdrant,
            collection_name="human-nutrition-text.pdf",
            embedding=st.session_state.embeddings,
            sparse_embedding=st.session_state.sparse_embeddings,
            retrieval_mode=RetrievalMode.HYBRID,
            vector_name="dense",
            sparse_vector_name="sparse"
        )
        
        # Kết nối Neo4j
        st.session_state.driver = GraphDBConnection(
            uri="bolt://localhost:7687",
            username="neo4j",
            password=os.environ.get("NEO4J_PASSWORD"),
            database="graduation"
        )
        st.session_state.graph = st.session_state.driver.connect_to_graph()
        st.session_state.driver.setup_index()
        st.session_state.initialized = True

        #Initialize RAGPipeline
        # st.session_state.react_pipeline = ReActPipeline(vector_store=st.session_state.vectordb,
        #                                                 client=st.session_state.client)
        #Initialize web search
        # st.session_state.driver = chrome()
# Gọi hàm khởi tạo
initialize_connections()

# === Các hàm xử lý ===
def stream(query: str, temperature: Optional[float] = 0.5):
    response = st.session_state.client.chat.completions.create(
        model='qwen2.5:3b',
        messages=[{"role": "user", "content": query}],
        max_tokens=2048,
        stream=True,
        temperature=temperature,
    )
    collected_message = ""
    for chunk in response:
        if chunk.choices and len(chunk.choices) > 0:
            content = chunk.choices[0].delta.content or ""
            if content:
                print(content, end="", flush=True)
                collected_message += content
                time.sleep(0.01)
    return collected_message

def ask(query: str, temperature: Optional[float] = 0.5):
    response = st.session_state.client.chat.completions.create(
        model='qwen2.5:3b',
        messages=[{"role": "user", "content": query}],
        max_tokens=2048,
        temperature=temperature,
    )
    answer = response.choices[0].message.content
    return answer
def handle_llm(new_query):
    new_prompt = llm_prompt.format(query=new_query)
    response = st.session_state.gemini.models.generate_content(
        model="gemini-2.0-flash",
        contents=new_prompt,
    )
    answer = response.text
    return answer

def handle_rag( new_query,selected_doc_ids: list =None):
    
    output=""

    context = full_retriever(st.session_state.graph, st.session_state.vectordb, new_query,selected_doc_ids)
    new_prompt_doc = enhancing_prompt.format(query=new_query, context= context)
    document_answer= stream(new_prompt_doc,0.1)
    
    #seach website
    links= seach_web(query=new_query, api_key=api_key, max_results=5)
    web_content = ""
    for link in links:
        content = read_web(url=link)
        
        # Kiểm tra xem kết quả trả về có phải là một chuỗi hay không
        if isinstance(content, str):  
            web_content += content  
        else:
            # Nếu không phải chuỗi (chẳng hạn nếu là lỗi), xử lý lỗi ở đây
            print(f"Error reading URL {link}: {content}")  # Hoặc bạn có thể ghi vào log hoặc thông báo lỗi
    new_prompt_web= enhancing_prompt.format(query=new_query, context= web_content)
    web_search_answer = stream(new_prompt_web,0.1)
    link_output = "Relevant web search links:\n\n"
    for idx,link in enumerate(links):
        link_list = f"Source{idx+1}: {link}"
        link_output += link_list + "\n\n"
    output = "DOCUMENT_ANSWER:\n" + document_answer + "\n\n" + "WEB SEARCH ANSWER:\n" + web_search_answer + "\n\n" + link_output
    return output
    
    # return output
    # output= st.session_state.react_pipeline.stream(
    #     original_question=new_query,
    #     messages=[{"role": "user", "content": new_query}],
    #     top_k=5,
    #     doc_ids=selected_doc_ids
    # )
    # return output

def handle_calendar(new_query):
    new_prompt = schedule_prompt(new_query)
    response = st.session_state.gemini.models.generate_content(
        model="gemini-2.0-flash",
        contents=new_prompt,
        config={'response_mime_type': 'application/json'}
    )
    events = json.loads(response.text)
    json_explain_prompt = process_json_ouput(events)
    answer = ask(json_explain_prompt, 0.1)
    print("\nEvents:\n", events)
    output = ""
    for event in events:
        operation = event['operation']
        if operation == "CREATE":
            output = st.session_state.calendar_agent.insert_event(event)
        elif operation == "UPDATE":
            output= st.session_state.calendar_agent.update_event(event)
        elif operation== "DELETE":
            output == st.session_state.calendar_agent.delete_event(json_input=event)
        elif operation == "READ":
            output, has_events = st.session_state.calendar_agent.list_event(json_input=event)
    return output

def embed_file(uploaded_file, existed_docs, qdrant_client, embeddings, sparse_embeddings):
    os.makedirs("./tmp", exist_ok=True)
    
    file_path = f"./tmp/{uploaded_file.name}"
    with open(file_path, "wb") as f:
        f.write(uploaded_file.read())

    # Process PDF using the same logic as pdf_processing.py
    documents = process_pdf_to_documents(file_path)
    # Create collection if it doesn't exist
    result = create_vectordb(client=qdrant_client, 
                    collection_name=None,
                    documents=documents, 
                    existed_docs=existed_docs,
                    embeddings=embeddings,
                    sparse_embeddings=sparse_embeddings)
    try:
        os.remove(file_path)
    except:
        pass
    return result

def process_file_async(uploaded_file, existed_docs, status_queue, qdrant_client, embeddings, sparse_embeddings):
    try:
        status_queue.put(("info", "🔄 Ingesting document..."))
        result = embed_file(uploaded_file, existed_docs, qdrant_client, embeddings, sparse_embeddings)
        # Clear the initial status message
        status_queue.put(("clear", ""))
        
        # Add a small delay to ensure clear message is processed
        time.sleep(0.1)
        
        if result:
            print("Result from embed_file:", result)  # Debug print
            status_queue.put(("info", result))
            time.sleep(5)
            status_queue.put(("clear", ""))
        else:
            status_queue.put(("success", "✅ Successfully ingested document!"))
            print("Successfully ingested document!")
        
    except Exception as e:
        error_msg = f"❌ Error ingesting document: {str(e)}"
        status_queue.put(("error", error_msg))
        time.sleep(5)
        print("Error:", error_msg)  # Debug print
        status_queue.put(("clear", ""))

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


# === Giao diện Streamlit ===
st.set_page_config(page_title="Nutrition Virtual Assistant", layout="wide")
st.title("🧠 Nutrition VA: Nutritional advice and personal schedule support")

# Sidebar - Upload file PDF và hiển thị danh sách tài liệu
with st.sidebar:
    if st.button(" New Chat"):
        st.session_state.chat_history = []
        st.session_state.his_agent.delete_history
    st.markdown("### 📚 Documents list existed in vector database:")
    try:
        existed_docs = get_all_doc_ids_from_collection(
            qdrant_client=st.session_state.qdrant,
            collection_name="human-nutrition-text.pdf",
            limit=10
        )
        if existed_docs:
            selected_doc_ids = st.multiselect(
                label="Select documents to answer",
                options=existed_docs,
                default=[]
            )
            st.session_state.selected_doc_ids = selected_doc_ids
        else:
            st.info("There is no document in vector database.")
            st.session_state.selected_doc_ids = []
    except Exception as e:
        st.error(f"Lỗi khi truy xuất tài liệu: {str(e)}")
        st.session_state.selected_doc_ids = []
    st.header("📎 Upload documents")
    uploaded_file = st.file_uploader("Upload PDF", type=["pdf"])
    
    # Khởi tạo status queue nếu chưa có
    if 'status_queue' not in st.session_state:
        st.session_state.status_queue = Queue()
    
    # Kiểm tra và hiển thị thông báo từ queue
    try:
        while not st.session_state.status_queue.empty():
            status_type, message = st.session_state.status_queue.get_nowait()
            if status_type == "info":
                st.info(message)
            elif status_type == "success":
                st.success(message)
            elif status_type == "error":
                st.error(message)
    except:
        pass
    
    if uploaded_file:
        # Create a placeholder for status messages
        status_placeholder = st.empty()
        
        # Tạo thread mới để xử lý file
        thread = threading.Thread(
            target=process_file_async,
            args=(
                uploaded_file, 
                existed_docs, 
                st.session_state.status_queue,
                st.session_state.qdrant,
                st.session_state.embeddings,
                st.session_state.sparse_embeddings
            ),
            daemon=True  # Thêm daemon=True để thread tự động kết thúc khi chương trình chính kết thúc
        )
        thread.start()
        
        # Monitor the status queue and update the UI
        while thread.is_alive():
            try:
                while not st.session_state.status_queue.empty():
                    status_type, message = st.session_state.status_queue.get_nowait()
                    print(f"Processing message: {status_type} - {message}")  # Debug print
                    if status_type == "clear":
                        status_placeholder.empty()
                    elif status_type == "info" and message:  # Only show non-empty messages
                        status_placeholder.info(message)
                    elif status_type == "success":
                        status_placeholder.success(message)
                    elif status_type == "error":
                        status_placeholder.error(message)
            except Exception as e:
                print(f"Error in status queue processing: {str(e)}")  # Debug print
                pass
            time.sleep(0.1)
        
        # Clear the status placeholder after processing
        status_placeholder.empty()

    # Tùy chọn chọn route xử lý
    if existed_docs:  # Nếu có doc_ids, cho phép chọn "RAG"
        route_options=["LLM (answer without retrieving documents)", "RAG (Augmented Generation with Retrieving documents)", "Calendar (Supporting manage personal schedule)"]
    else:
        route_options = ["LLM (answer without retrieving documents)", "Calendar (Supporting manage personal schedule)"]
    
    route_answer = st.radio(
        label="Select processing method",  # Thêm label
        options=route_options,
        label_visibility="visible"  # Đảm bảo label hiển thị
    )

# === Giao diện Chat kiểu ChatGPT ===

# Khởi tạo lịch sử chat nếu chưa có
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

# Hiển thị các tin nhắn cũ
for msg in st.session_state.chat_history:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# Hộp nhập tin nhắn từ người dùng
user_query = st.chat_input("Typing question...")

# Xử lý khi người dùng gửi câu hỏi
if user_query:
    with st.chat_message("user"):
        st.markdown(user_query)
        thinking_placeholder = st.empty()  # Tạo placeholder cho "Thinking..."

    thinking_html = """
    <div class="thinking-blink" style="font-weight:bold; font-size: 1.1em;">
      Thinking<span class="dot-1">.</span><span class="dot-2">.</span><span class="dot-3">.</span>
    </div>
    <style>
    @keyframes blink {
      0% { opacity: 0.2; }
      50% { opacity: 1; }
      100% { opacity: 0.2; }
    }
    .thinking-blink { animation: blink 1s infinite; }
    .dot-1 { animation: none; }
    .dot-2 { animation: none; }
    .dot-3 { animation: none; }
    </style>
    """
    thinking_placeholder.markdown(thinking_html, unsafe_allow_html=True)  # Hiển thị hiệu ứng động

    # Tạo câu hỏi mới dựa vào agent context-aware
    new_query = st.session_state.his_agent.generate_reply(user_query)
    st.session_state.his_agent.add_to_history("user", new_query)
    print("\nNew-query:",new_query)
    route_query = router_query(new_query)
    print("\nRoute query:", route_query)
    if route_query== "chitchat":
        output= "As an Nutrition Virtual Assistant, I can provide nutritional advice and personal schedule support. However, I cannot answer this question without retrieving relevant documents from the vector database. Please select the appropriate route for processing."
    elif route_query == "nutrition": 
        route_answer= route_answer
        print("\nRoute answer:", route_answer)
        if route_answer == "LLM (answer without retrieving documents)":
            output = handle_llm(new_query)
        elif route_answer == "RAG (Augmented Generation with Retrieving documents)":
            selected_docs=st.session_state.get("selected_doc_ids", [])
            output = handle_rag( new_query,selected_docs)
        elif route_answer == "Calendar (Supporting manage personal schedule)":
            output = "This query is related to nutrition. Please select the appropriate route for processing."
    else:
        if route_answer== "LLM (answer without retrieving documents)":
            output = handle_llm(new_query)
        elif route_answer== "RAG (answer with retrieving documents from vectorDB)":
            selected_docs=st.session_state.get("selected_doc_ids", [])
            output = handle_rag( new_query,selected_docs)
        else: 
            output = handle_calendar(new_query)
    st.session_state.his_agent.add_to_history("assistant", output)

    thinking_placeholder.empty()  # Xóa/thay thế "Thinking..." sau khi có output

    # Hiển thị phản hồi
    with st.chat_message("assistant"):
        st.markdown(output)

    # Lưu vào session_state để hiển thị lại sau
    st.session_state.chat_history.append({"role": "user", "content": user_query})
    st.session_state.chat_history.append({"role": "assistant", "content": output})

# Hiển thị lịch sử chat
if st.session_state.history_chat:
    st.markdown("### 📜 Chat History")
    for message in st.session_state.history_chat:
        st.write(message)