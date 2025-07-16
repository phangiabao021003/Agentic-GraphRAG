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
        st.session_state.embeddings = HuggingFaceEmbeddings(model_name="BAAI/bge-m3")
        st.session_state.sparse_embeddings = FastEmbedSparse(model_name="Qdrant/bm25")
        st.session_state.calendar_agent = GoogleCalendar()
        st.session_state.history_chat = []
        st.session_state.his_agent = ContextAwareAgent(client=st.session_state.client, max_context_tokens=4000)
        
        # Khởi tạo Qdrant
        st.session_state.qdrant = QdrantClient(host="localhost", port=6333)
        st.session_state.vectordb = QdrantVectorStore(
            client=st.session_state.qdrant,
            collection_name="human-nutrition.pdf",
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
    for chunk in response:
        if chunk.choices and len(chunk.choices) > 0:
            content = chunk.choices[0].delta.content or ""
            if content:
                yield content

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
    language = st.session_state.get('language', 'English')
    links= seach_web(query=new_query, api_key=api_key, max_results=5)
    web_content = ""
    for link in links:
        content = read_web(url=link)
        if isinstance(content, str):  
            web_content += content  
        else:
            print(f"Error reading URL {link}: {content}")
    new_prompt_web= enhancing_prompt.format(query=new_query, context= web_content, language=language)
    new_prompt = llm_prompt.format(query=new_query, language=language)
    response = st.session_state.gemini.models.generate_content(
        model="gemini-2.0-flash",
        contents=new_prompt,
    )
    link_output = "Relevant web search links:\n\n"
    for idx,link in enumerate(links):
        link_list = f"Source{idx+1}: {link}"
        link_output += link_list + "\n\n"
    answer = response.text
    return answer, new_prompt_web, link_output

def handle_rag(new_query, selected_doc_ids: list = None):
    language = st.session_state.get('language', 'English')
    context = full_retriever(st.session_state.vectordb, new_query, selected_doc_ids)
    new_prompt_doc = enhancing_prompt.format(query=new_query, context=context, language=language)
    links = seach_web(query=new_query, api_key=api_key, max_results=5)
    web_content = ""
    for link in links:
        content = read_web(url=link)
        if isinstance(content, str):  
            web_content += content  
        else:
            print(f"Error reading URL {link}: {content}")
    new_prompt_web = enhancing_prompt.format(query=new_query, context=web_content, language=language)
    link_output = "Relevant web search links:\n\n"
    for idx, link in enumerate(links):
        link_list = f"Source{idx+1}: {link}"
        link_output += link_list + "\n\n"
    return new_prompt_doc, new_prompt_web, link_output

def handle_calendar(new_query):
    language = st.session_state.get('language', 'English')
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
            output = st.session_state.calendar_agent.update_event(event)
        elif operation == "DELETE":
            output = st.session_state.calendar_agent.delete_event(json_input=event)
        elif operation == "READ":
            output, has_events = st.session_state.calendar_agent.list_event(json_input=event)
    # Nếu chọn tiếng Việt, dịch output sang tiếng Việt
    if language == "Vietnamese" and output:
        translate_prompt = f"Dịch sang tiếng Việt: {output}. Chỉ đưa ra kết quả dịch cuối cùng"
        # Sử dụng Gemini để dịch
        try:
            translated = st.session_state.gemini.models.generate_content(
                model="gemini-2.0-flash",
                contents=translate_prompt
            )
            output = translated.text
        except Exception as e:
            output = output + "\n(Lỗi khi dịch sang tiếng Việt)"
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
    st.markdown("### 📚 Existed knowledge of nutrition virtual assistant")
    try:
        # Dropdown chọn ngôn ngữ
        language = st.selectbox(
            label="Select language / Chọn ngôn ngữ",
            options=["English", "Vietnamese"],
            index=0 if st.session_state.get('language', 'English') == 'English' else 1
        )
        st.session_state['language'] = language
        # Lấy existed_docs từ session_state nếu có, nếu không thì gọi hàm
        existed_docs = st.session_state.get('existed_docs')
        if existed_docs is None:
            try:
                existed_docs = get_all_doc_ids_from_collection(
                    qdrant_client=st.session_state.qdrant,
                    collection_name="human-nutrition.pdf",
                    limit=10
                )
                st.session_state['existed_docs'] = existed_docs
            except Exception as e:
                st.error(f"Lỗi khi truy xuất tài liệu: {str(e)}")
                existed_docs = []
                st.session_state['existed_docs'] = []
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
                # Lấy lại danh sách tài liệu mới nhất và lưu vào session_state
                existed_docs = get_all_doc_ids_from_collection(
                    qdrant_client=st.session_state.qdrant,
                    collection_name="human-nutrition.pdf",
                    limit=10
                )
                st.session_state['existed_docs'] = existed_docs
            elif status_type == "error":
                st.error(message)
    except:
        pass
    
    if uploaded_file:
        # Create a placeholder for status messages
        status_placeholder = st.empty()
        
        # Tạo thread mới để xử lý file (chỉ tạo nếu chưa có thread đang chạy)
        if 'ingest_thread' not in st.session_state or not st.session_state['ingest_thread'].is_alive():
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
                daemon=True
            )
            thread.start()
            st.session_state['ingest_thread'] = thread

        # Hiển thị status từ queue (nếu có)
        import time as _time
        show_success = False
        success_time = None
        try:
            while not st.session_state.status_queue.empty():
                status_type, message = st.session_state.status_queue.get_nowait()
                if status_type == "clear":
                    status_placeholder.empty()
                elif status_type == "info" and message:
                    status_placeholder.info(message)
                elif status_type == "success":
                    status_placeholder.success(message)
                    show_success = True
                    success_time = _time.time()
                    # Lấy lại danh sách tài liệu mới nhất và lưu vào session_state
                    existed_docs = get_all_doc_ids_from_collection(
                        qdrant_client=st.session_state.qdrant,
                        collection_name="human-nutrition.pdf",
                        limit=10
                    )
                    st.session_state['existed_docs'] = existed_docs
                elif status_type == "error":
                    status_placeholder.error(message)
        except:
            pass

        # Nếu vừa ingest xong, hiển thị success 5 giây rồi ẩn
        if show_success and success_time:
            if _time.time() - success_time > 5:
                status_placeholder.empty()

    # Tùy chọn chọn route xử lý
    if existed_docs:  # Nếu có doc_ids, cho phép chọn "RAG"
        route_options=["Answer without using existed documents", "Answer using existed documents", "Supporting manage personal schedule"]
    else:
        route_options = ["Answer without using existed documents", "Supporting manage personal schedule"]
    
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

    new_query = st.session_state.his_agent.generate_reply(user_query)
    st.session_state.his_agent.add_to_history("user", new_query)
    print("\nNew-query:", new_query)
    route_query = router_query(new_query)
    print("\nRoute query:", route_query)
    output = ""
    if route_query == "chitchat":
        output = "As an Nutrition Virtual Assistant, I can provide nutritional advice and personal schedule support. However, I cannot answer this question without retrieving relevant documents from the vector database. Please select the appropriate route for processing."
        with st.chat_message("assistant"):
            st.markdown(output)
        st.session_state.his_agent.add_to_history("assistant", output)
        st.session_state.chat_history.append({"role": "user", "content": user_query})
        st.session_state.chat_history.append({"role": "assistant", "content": output})
        thinking_placeholder.empty()
    elif route_query == "nutrition":
        route_answer = route_answer
        print("\nRoute answer:", route_answer)
        if route_answer == "Answer without using existed documents":
            answer, new_prompt_web, link_output = handle_llm(new_query)
            with st.chat_message("assistant"):
                assistant_placeholder = st.empty()
                output = answer
                assistant_placeholder.markdown(output)
                output += "\n\nWEB SEARCH ANSWER:\n"
                for chunk in stream(new_prompt_web, 0.1):
                    output += chunk
                    assistant_placeholder.markdown(output)
                output += "\n\n" + link_output
                assistant_placeholder.markdown(output)
            st.session_state.his_agent.add_to_history("assistant", output)
            st.session_state.chat_history.append({"role": "user", "content": user_query})
            st.session_state.chat_history.append({"role": "assistant", "content": output})
            thinking_placeholder.empty()
        elif route_answer == "Answer using existed documents":
            new_prompt_doc, new_prompt_web, link_output = handle_rag(new_query, st.session_state.get("selected_doc_ids", []))
            with st.chat_message("assistant"):
                assistant_placeholder = st.empty()
                output = "DOCUMENT_ANSWER:\n"
                for chunk in stream(new_prompt_doc, 0.1):
                    output += chunk
                    assistant_placeholder.markdown(output)
                output += "\n\nWEB SEARCH ANSWER:\n"
                for chunk in stream(new_prompt_web, 0.1):
                    output += chunk
                    assistant_placeholder.markdown(output)
                output += "\n\n" + link_output
                assistant_placeholder.markdown(output)
            st.session_state.his_agent.add_to_history("assistant", output)
            st.session_state.chat_history.append({"role": "user", "content": user_query})
            st.session_state.chat_history.append({"role": "assistant", "content": output})
            thinking_placeholder.empty()
        elif route_answer == "Supporting manage personal schedule":
            output = "This query is related to nutrition. Please select the appropriate route for processing."
            with st.chat_message("assistant"):
                st.markdown(output)
            st.session_state.his_agent.add_to_history("assistant", output)
            st.session_state.chat_history.append({"role": "user", "content": user_query})
            st.session_state.chat_history.append({"role": "assistant", "content": output})
            thinking_placeholder.empty()
    else:
        if route_answer == "Answer without using existed documents":
            answer, new_prompt_web, link_output = handle_llm(new_query)
            with st.chat_message("assistant"):
                assistant_placeholder = st.empty()
                output = answer
                assistant_placeholder.markdown(output)
                output += "\n\nWEB SEARCH ANSWER:\n"
                for chunk in stream(new_prompt_web, 0.1):
                    output += chunk
                    assistant_placeholder.markdown(output)
                output += "\n\n" + link_output
                assistant_placeholder.markdown(output)
            st.session_state.his_agent.add_to_history("assistant", output)
            st.session_state.chat_history.append({"role": "user", "content": user_query})
            st.session_state.chat_history.append({"role": "assistant", "content": output})
            thinking_placeholder.empty()
        elif route_answer == "Answer using existed documents":
            new_prompt_doc, new_prompt_web, link_output = handle_rag(new_query, st.session_state.get("selected_doc_ids", []))
            with st.chat_message("assistant"):
                assistant_placeholder = st.empty()
                output = "DOCUMENT_ANSWER:\n"
                for chunk in stream(new_prompt_doc, 0.1):
                    output += chunk
                    assistant_placeholder.markdown(output)
                output += "\n\nWEB SEARCH ANSWER:\n"
                for chunk in stream(new_prompt_web, 0.1):
                    output += chunk
                    assistant_placeholder.markdown(output)
                output += "\n\n" + link_output
                assistant_placeholder.markdown(output)
            st.session_state.his_agent.add_to_history("assistant", output)
            st.session_state.chat_history.append({"role": "user", "content": user_query})
            st.session_state.chat_history.append({"role": "assistant", "content": output})
            thinking_placeholder.empty()
        else:
            output = handle_calendar(new_query)
            with st.chat_message("assistant"):
                st.markdown(output)
            st.session_state.his_agent.add_to_history("assistant", output)
            st.session_state.chat_history.append({"role": "user", "content": user_query})
            st.session_state.chat_history.append({"role": "assistant", "content": output})
            thinking_placeholder.empty()

# Hiển thị lịch sử chat
if st.session_state.history_chat:
    st.markdown("### 📜 Chat History")
    for message in st.session_state.history_chat:
        st.write(message)