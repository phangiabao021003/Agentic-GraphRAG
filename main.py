from graph.graphdb_connection import GraphDBConnection
import os
from agents.agent_router import router_query,router_output
import json
from graph.entity_extractor import full_retriever
from prompt import enhancing_prompt, llm_prompt, schedule_prompt,process_calendar_query
from dotenv import load_dotenv
from openai import OpenAI
import time
from agents.agent_history import ContextAwareAgent
from qdrant_client import QdrantClient
from langchain.embeddings.ollama import OllamaEmbeddings
from langchain_qdrant import FastEmbedSparse, QdrantVectorStore, RetrievalMode
from langchain_community.embeddings import HuggingFaceEmbeddings
from calendar_tool.agent_calendar import GoogleCalendar
from google import genai


load_dotenv()

gemini = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
client = OpenAI(
    base_url='http://localhost:11434/v1',
    api_key='dolphin-llama3'
)

calendar_agent= GoogleCalendar()

# embeddings = OllamaEmbeddings(model="bge-m3")
embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-mpnet-base-v2")
sparse_embeddings = FastEmbedSparse(model_name="Qdrant/bm25")



his_agent=ContextAwareAgent(client)

vectordb = QdrantClient(path="./vectordb")
# Tạo vector store từ client và collection đã tồn tại
# vector_store = QdrantVectorStore(
#     client=vectordb,
#     collection_name="Nutrition",
#     embedding=embeddings,
#     retrieval_mode=RetrievalMode.DENSE,
# )
qdrant = QdrantVectorStore(
        client=vectordb,
        collection_name="Nutritionv5",
        embedding=embeddings,
        sparse_embedding=sparse_embeddings,
        retrieval_mode=RetrievalMode.HYBRID,
        vector_name="dense",
        sparse_vector_name="sparse")

password = os.environ.get("NEO4J_PASSWORD")
driver = GraphDBConnection(
    uri="bolt://localhost:7687",
    username="neo4j",
    password=password,
    database="graduation"
)

# Kết nối
graph = driver.connect_to_graph()

# Tạo index nếu cần
driver.setup_index()
# Đóng kết nối khi xong
driver.close()

# Example usage of the entity extractor

def ask(query,temperature):
    response = client.chat.completions.create(
        model='llama3.2',
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
                print(content, end="", flush=True)  # In ngay ra console
                collected_message += content
                time.sleep(0.01)  # Thêm độ trễ giữa các chunk để dễ đọc hơn
    return collected_message
while True:
    # Nhập câu hỏi từ người dùng
    query = input("\n\nUser: ")
    if query.lower() == "exit":
        break
    new_query = his_agent.generate_reply(query)
    #print(f"\nRelevant history: {relevant_history}")
    print(f"\nNew query: {new_query}")
    route= router_query(new_query)
    #check history conversation
    his_agent.add_to_history("user", new_query)
    if route == "llm":
        print("llm detected.")
        new_prompt=llm_prompt(new_query, context=None)
        answer=ask(new_prompt,0.5) 
        his_agent.add_to_history("assistant", answer) # Sau khi kết thúc stream, thêm assistant reply vào lịch sử
 
    elif route == "rag":
        print("RAG detected.")
        context=full_retriever(graph,qdrant,query)
        new_prompt=enhancing_prompt(new_query, context)
        answer=ask(new_prompt,0.1)  
    elif route == "calendar":
        print("Schedule detected.")
        processed_query=process_calendar_query(query)
        answer=ask(processed_query,0.1)
        new_prompt=schedule_prompt(answer)
        response = gemini.models.generate_content(
            model="gemini-2.0-flash", 
            contents=new_prompt,  
            config={'response_mime_type': 'application/json'}
        )
        events=response.text
        print("\nEvents:\n",events)
        events = json.loads(events)
        for event in events:
            if event['operation'] == 'CREATE':
                print("\nTask detected:", event['operation'])
                # calendar_agent.insert_event(event)    
            elif event['operation'] == "UPDATE":
                print("\nTask detected:", event['operation'])
                # calendar_agent.update_event(events)
            elif event['operation'] == "DELETE":
                print("\nTask detected:", event['operation'])
                # calendar_agent.delete_event(events)y
            elif event['operation'] == "READ":
                print("\nTask detected:", event['operation'])
                calendar_agent.list_event(timeMin=None, timeMax=None, json_input=None)

        
        




