import os
from dotenv import load_dotenv
from openai import OpenAI
import time
import csv
from datetime import datetime
from graph.context_extractor import full_retriever
from config import enhancing_prompt
from qdrant_client import QdrantClient
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_qdrant import FastEmbedSparse, QdrantVectorStore, RetrievalMode
from graph.graphdb_connection import GraphDBConnection
from datasets import Dataset
import pandas as pd
import json
from ragas.metrics import (
    faithfulness,
    answer_relevancy,
    context_precision,
    context_recall
)
from ragas import evaluate
from ragas.llms import LangchainLLMWrapper
from ragas.embeddings import LangchainEmbeddingsWrapper
from langchain_ollama.chat_models import ChatOllama
import ast

# Load environment variables
load_dotenv()

# Initialize OpenAI client
client = OpenAI(
    base_url='http://localhost:11434/v1',
    api_key='dolphin-llama3'
)

# Initialize embeddings
embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-mpnet-base-v2")
sparse_embeddings = FastEmbedSparse(model_name="Qdrant/bm25")

# Initialize Qdrant client and vector store
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

# Initialize Neo4j connection
password = os.environ.get("NEO4J_PASSWORD")
driver = GraphDBConnection(
    uri="bolt://localhost:7687",
    username="neo4j",
    password=password,
    database="graduation"
)
graph = driver.connect_to_graph()
driver.setup_index()
driver.close()

def generate_answer(prompt, temperature=0.1):
    """Function to get response from LLM"""
    response = client.chat.completions.create(
        model='llama3.2',
        messages=[{"role": "user", "content": prompt}],
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

def generate_ground_truth(question, context):
    """Generate ground truth answer using GPT-4"""
    prompt = f"""You are a University Professor creating a test for advanced students.
For the given question and context, create a comprehensive answer that would be considered the ground truth.

Question: {question}
Context: {context}

Provide a detailed and accurate answer based solely on the context provided.
"""
    response = client.chat.completions.create(
        model='llama3.2',
        messages=[{"role": "user", "content": prompt}],
        max_tokens=2048,
        temperature=0.1,
    )
    return response.choices[0].message.content

def evaluate_ragas_dataset(dataset):
    """Evaluate RAG metrics using RAGAS"""
    print("\nEvaluating RAG metrics...")

    # Initialize Ollama LLM with increased timeout
    llm = ChatOllama(
        model="llama3.2",
        temperature=0,
        timeout=600,  # 10 minutes timeout
        request_timeout=600
    )
    ragas_llm = LangchainLLMWrapper(llm)

    # Use existing embeddings
    ragas_emb = LangchainEmbeddingsWrapper(embeddings)

    # Define metrics to evaluate
    metrics = [
        faithfulness,
        answer_relevancy,
        context_precision,
        context_recall
    ]
    try:
        result = evaluate(
            dataset,
            metrics=metrics,
            llm=ragas_llm,
            embeddings=ragas_emb
        )
    except Exception as e:
        print(f"Error evaluating RAGAS: {e}")
    return result

def load_dataset_from_csv(file_path):
    """Load dataset from a CSV file."""
    try:
        df = pd.read_csv(file_path)
        # Convert contexts column from JSON string to list
        if "contexts" in df.columns:
            df["contexts"] = df["contexts"].apply(lambda x: json.loads(x) if pd.notna(x) else [])
        if all(col in df.columns for col in ["question", "contexts", "answer", "reference"]):
            return Dataset.from_pandas(df)
        else:
            print("CSV file must contain columns: question, contexts, answer, reference")
            return None
    except FileNotFoundError:
        print(f"Error: File not found at {file_path}")
        return None

def save_dataset_to_csv_only_data(rows, filename):
    """Save dataset to CSV file"""
    df = pd.DataFrame(rows)
    df.to_csv(filename, index=False, encoding='utf-8')
    print(f"\nDataset saved (only data) to the file: {filename}")

def save_evaluation_to_csv( evaluation_result, filename):
    """Save evaluation results to CSV file"""
    # Convert evaluation result to pandas DataFrame
    eval_df = evaluation_result.to_pandas()
    
    # Save to CSV
    eval_df.to_csv(filename, index=False, encoding='utf-8')
    print(f"Saved the evaluation results to the file {filename}")

def main():
    questions = []
    contexts = []
    answers = []
    ground_truths = []
    rows = []

    print("Type the question, type 'created data' to load the CSV file, type 'exit' to end.")

    while True:
        user_input = input("\n\nUser: ").strip()

        if user_input.lower() == "exit":
            if rows:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                output_filename = f"dataset_data_only_{timestamp}.csv"
                save_dataset_to_csv_only_data(rows, output_filename)
            else:
                print("No data to save.")
            break

        elif user_input.lower() == "created data":
            csv_file_path = input("Type the path of the CSV file: ").strip()
            loaded_dataset = load_dataset_from_csv(csv_file_path)
            if loaded_dataset is not None:
                evaluation_result = evaluate_ragas_dataset(loaded_dataset)
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                eval_output_filename = f"evaluation_results_loaded_{timestamp}.csv"
                save_evaluation_to_csv(loaded_dataset, evaluation_result, eval_output_filename)
            else:
                print("Cannot load dataset from CSV. Please check the path or the format of the file.")
            continue

        else:
            # Luồng nhập câu hỏi bình thường
            question = user_input
            questions.append(question)
            context = full_retriever(graph, qdrant, question)
            print(f"\n[Context extracted]: {context}")
            contexts.append(context)

            new_prompt = enhancing_prompt(question, context)
            print("\n[Generating answer:]")
            answer = generate_answer(new_prompt)
            print("\n\n[Answer generated]\n")
            answers.append(answer)

            print("[Generating ground truth answer:]")
            ground_truth = generate_ground_truth(question, context)
            print(f"\n[Ground truth generated]:\n{ground_truth}")
            ground_truths.append(ground_truth)

            rows.append({
                "question": question,
                "contexts": [context],
                "answer": answer,
                "reference": ground_truth
            })

    if rows:
        evaluation_dataset = Dataset.from_list(rows)
        print(f"\nDataset created với {len(rows)} câu hỏi.")

        evaluation_result = evaluate_ragas_dataset(evaluation_dataset)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        eval_output_filename = f"evaluation_results_{timestamp}.csv"
        save_evaluation_to_csv( evaluation_result, eval_output_filename)

if __name__ == "__main__":
    main()
