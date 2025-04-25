import spacy
from keybert import KeyBERT
from pydantic import BaseModel, Field
from typing import List
import torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification
import torch
import json
# Load mô hình spaCy và KeyBERT
nlp = spacy.load("en_core_web_sm")
kw_model = KeyBERT()
tokenizer = AutoTokenizer.from_pretrained("BAAI/bge-reranker-base")
reranker = AutoModelForSequenceClassification.from_pretrained("BAAI/bge-reranker-base")
reranker.eval()

class Entities(BaseModel):
    """Danh sách tên thực thể + khái niệm + chủ đề."""
    names: List[str] = Field(..., description="All entities, concepts, and keywords extracted from the text.")

def extract_entities(text: str) -> Entities:
    doc = nlp(text)

    # Lấy thực thể NER
    ner_entities = {ent.text.strip() for ent in doc.ents}

    # Lấy noun chunks (cụm danh từ)
    noun_chunks = {chunk.text.strip() for chunk in doc.noun_chunks}

    # Lấy từ khóa bằng KeyBERT
    keywords = {kw[0].strip() for kw in kw_model.extract_keywords(text, stop_words='english', top_n=5)}

    # Gộp tất cả vào một tập hợp duy nhất
    combined = ner_entities.union(noun_chunks).union(keywords)

    return Entities(names=list(combined))

# Fulltext index query
def graph_retriever(question, graph) -> str:
    """
    Collects the neighborhood of entities mentioned
    in the question
    """
    result = ""
    entities = extract_entities(question)
    for entity in entities.names:
        response = graph.query(
            """CALL db.index.fulltext.queryNodes('fulltext_entity_id', $query, {limit:2})
            YIELD node,score
            CALL {
              WITH node
              MATCH (node)-[r:!MENTIONS]->(neighbor)
              RETURN node.id + ' - ' + type(r) + ' -> ' + neighbor.id AS output
              UNION ALL
              WITH node
              MATCH (node)<-[r:!MENTIONS]-(neighbor)
              RETURN neighbor.id + ' - ' + type(r) + ' -> ' +  node.id AS output
            }
            RETURN output LIMIT 50
            """,
            {"query": entity},
        )
        result += "\n".join([el['output'] for el in response])
    return result
def rerank(query, docs, model, tokenizer, top_k=4):
    pairs = [(query, doc.page_content) for doc in docs]
    with torch.no_grad():
        inputs = tokenizer(pairs, padding=True, truncation=True, return_tensors='pt', max_length=512)
        scores = model(**inputs, return_dict=True).logits.view(-1, ).float()

    scored_docs = list(zip(docs, scores.tolist()))
    reranked = sorted(scored_docs, key=lambda x: x[1], reverse=True)
    return [doc for doc, score in reranked[:top_k]]

def full_retriever(graph,vector_store,question):
    # graph_data = graph_retriever(question,graph)
    vector_data = vector_store.similarity_search(question, k=7)
    reranked_docs = rerank(question, vector_data, reranker, tokenizer, top_k=3)
    cleaned_contents = []
    for doc in reranked_docs:
        content = doc.page_content.replace("\n", " ")
        cleaned_contents.append(f"- {content}")

    joined_contents = "\n".join(cleaned_contents)
    # final_data = f"""Graph data:
    # {graph_data}
    # Vector data:
    # {joined_contents}"""
    return joined_contents
def enhancing_prompt(query, context):

    # base_prompt=f"""Based on the context provided, please completely and relevant answer the user's question.
    # Your answer should be based on the context and chat history, not on any external information.
    # If no information in the context relates to the question, respond with "The document does not contain the information mentioned in the question".
    # Now use the following context and chat history items to answer the user query
    # Chat history:
    # {chat_history}
    # Context:
    # {context}
    # Query: {query}
    # Answer: """
    base_prompt=f"""You are a helpful AI assistant that is very good in explaining and expressing answer for anything asked by the user in English.
user will ask question as: {query}
you must give answer with detailed explanation with bullets, heading , subheading etc. based on the context only, not on any external information.
always rename the title ,headings, subheading in your answer but keep the meaning same.
ONLY use relevant information with the query from the context to answer.
if no related information found just reply with "The document does not contain the information mentioned in the question"
you must follow this  very stricty , dont use anything else other than the given context :
###
CONTEXT:
{context}
###
ANSWER:
"""
    return base_prompt
