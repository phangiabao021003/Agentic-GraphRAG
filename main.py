from graph.graphdb_connection import GraphDBConnection
import os
from agents.agent_router import classify_user_input
import json
from graph.entity_extractor import enhancing_prompt,full_retriever
from dotenv import load_dotenv
from openai import OpenAI
import time
from agents.agent_history import ContextAwareAgent
from qdrant_client import QdrantClient
from langchain.embeddings.ollama import OllamaEmbeddings
from langchain_qdrant import FastEmbedSparse, QdrantVectorStore, RetrievalMode


load_dotenv()


client = OpenAI(
    base_url='http://localhost:11434/v1',
    api_key='dolphin-llama3'
)
embeddings = OllamaEmbeddings(model="bge-m3")
sparse_embeddings = FastEmbedSparse(model_name="Qdrant/bm25")



his_agent=ContextAwareAgent(client)

vectordb = QdrantClient(path="C:/Users/bao.phangia/Downloads/Đồ án/vectordb")
# Tạo vector store từ client và collection đã tồn tại
# vector_store = QdrantVectorStore(
#     client=vectordb,
#     collection_name="Nutrition",
#     embedding=embeddings,
#     retrieval_mode=RetrievalMode.DENSE,
# )
vector_store = QdrantVectorStore(
    client=vectordb,
    collection_name="Nutrition",
    embedding=embeddings,
    sparse_embedding=sparse_embeddings,
    retrieval_mode=RetrievalMode.DENSE,
)
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

def ask(query,new_query,his_agent,temperature):
    his_agent.add_to_history("user", query)
    response = client.chat.completions.create(
        model='llama3-chatqa',
        messages=[{"role": "user", "content": new_query}],
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
    his_agent.add_to_history("assistant", collected_message) # Sau khi kết thúc stream, thêm assistant reply vào lịch sử


while True:
    # Nhập câu hỏi từ người dùng
    query = input("\n\nUser: ")
    if query.lower() == "exit":
        conversation_history=[{"role": "system", "content": "You are a helpful virtual assistant."}]  # Reset lịch sử hội thoại
        break
    new_query = his_agent.generate_reply(query)
    #print(f"\nRelevant history: {relevant_history}")
    print(f"\nNew query: {new_query}")
    route= classify_user_input(new_query)
    #check history conversation
    if route == "llm":
        print("llm detected.")
        new_query=enhancing_prompt(new_query, context=None)
        # print(f"""\n###New query:\n {new_query}""")
        ask(query,new_query,his_agent,0.5)  
    elif route == "rag":
        print("RAG detected.")
        context=full_retriever(graph,vector_store,query)
        print(f"""\n###Context:\n {context}""")
        new_query=enhancing_prompt(new_query, context)
        # print(f"""\n###New query:\n {new_query}""")
        ask(query,new_query,his_agent,0.1)  
    else:
        print("Invalid route. Please check the classification.")
    
    #Classify the query
    
# query="What is AI?"
# route= classify_user_input(query)  
# if route == "chitchat":
#     ask(query,conversation_history,0.5)  # Gọi hàm xử lý câu hỏi chitchat
# elif route == "rag":
#     new_query=enhancing_prompt(query)
#     ask(new_query,conversation_history,0.1)  # Thêm độ trễ giữa các chunk để dễ đọc hơn
# else:
#     print("Invalid route. Please check the classification.")




