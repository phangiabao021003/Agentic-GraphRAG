import spacy
from keybert import KeyBERT
from pydantic import BaseModel, Field
from typing import List
import torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification
import torch
import datetime
import json
# Load mô hình spaCy và KeyBERT
nlp = spacy.load("en_core_web_sm")
kw_model = KeyBERT()
tokenizer = AutoTokenizer.from_pretrained("BAAI/bge-reranker-v2-m3")
reranker = AutoModelForSequenceClassification.from_pretrained("BAAI/bge-reranker-v2-m3")
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
    # final_data = f"""
    # ##
    # Graph data:
    # {graph_data}`
    # ##    
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
    base_prompt=f"""You are a helpful AI assistant that is very good in explaining and expressing answer.
you must give answer with detailed explanation based on the CONTEXT as possible.
Give yourself room to think by extracting relevant passages from the context than use them to answer the query.
Don't return the thinking, only return the answer.
ONLY USING RELEVANT PASSAGES to answer the question.
if no relevant information found from CONTEXT just reply with "The document does not contain the information mentioned in the question"
###
QUERY: 
{query}
###
CONTEXT:
{context}
###
RELEVANT PASSAGES: <extract relevant passages from the context here>
###
ANSWER:
"""
    return base_prompt
def llm_prompt(query, context):

    base_prompt=f"""You are a helpful AI assistant that is very good in explaining and expressing answer.
you must give answer with detailed explanation with bullets, heading , subheading etc. based on the CONTEXT.
always rename the title ,headings, subheading in your answer but keep the meaning same.
make sure your answers are as explanatory as possible.
###
QUERY: 
{query}
###
CONTEXT:
{context}
###
ANSWER:
"""
    return base_prompt
import datetime
import pytz

def schedule_prompt(user_query):
    """
    Generate an English prompt for Google Calendar Agent with:
    - Natural language understanding
    - CRUD operation classification
    - Standard Google Calendar API JSON output
    - Real-time timezone handling (Asia/Ho_Chi_Minh)
    - Recurring event support (ONLY IF ANY OR MENTIONED IN QUERY)
    """
    
    current_time = datetime.datetime.now(pytz.timezone('Asia/Ho_Chi_Minh')).strftime('%Y-%m-%d %H:%M:%S')
    
    prompt = f"""You are a professional Google Calendar Agent. Process the following request through these steps:

1. REQUEST ANALYSIS:
- User query: "{user_query}"
- Current time (Vietnam): {current_time}
- Detect operation type (CREATE/READ/UPDATE/DELETE)
- Identify elements:
  • Event name
  • Time (auto-calculate if vague)
  • Location
  • Attendees
  • Description
  • Recurrence (ONLY IF ANY OR MENTIONED IN QUERY)

2. CONVERSION RULES:
- Default timezone: Asia/Ho_Chi_Minh (+07:00)
- Time format: ISO 8601 (YYYY-MM-DDTHH:MM:SS+07:00)
- Default duration: 1 hour (if unspecified)
- Supports both English and Vietnamese

3. EXAMPLE OUTPUT STRUCTURE (ALWAYS USE JSON):
{{
  "operation": "CREATE|READ|UPDATE|DELETE",
  "parameters": {{
    // CREATE/UPDATE
    "summary": string,
    "description": string,
    "start": {{"dateTime": string, "timeZone": string}},
    "end": {{"dateTime": string, "timeZone": string}},
    "location": string,
    "attendees": [{{"email": string, "displayName": string}}],
    "colorId": integer (1-11),
    "recurrence": ["RRULE:FREQ=WEEKLY|MONTHLY..."],

    // READ
    "timeMin": string, // For query filtering
    "timeMax": string,
    "q": string, // Search keywords

    // UPDATE/DELETE
    "eventId": string // Required
  }},
  "metadata": {{
    "createdAt": "{current_time}",
    "timezone": "Asia/Ho_Chi_Minh",
    "defaultReminders": [{{"method": "popup", "minutes": 10}}]
  }}
}}

4. EXAMPLES:
{json.dumps({
    "CREATE": {
        "example_input": "Schedule meeting with Marketing team tomorrow 9am in Room 301",
        "output": {
            "operation": "CREATE",
            "parameters": {
                "summary": "Marketing Team Meeting",
                "location": "Room 301",
                "start": {"dateTime": "2023-10-17T09:00:00+07:00", "timeZone": "Asia/Ho_Chi_Minh"},
                "end": {"dateTime": "2023-10-17T10:00:00+07:00", "timeZone": "Asia/Ho_Chi_Minh"},
                "colorId": 2
            },
            "metadata": {"createdAt": current_time}
        }
    },
    "UPDATE": {
        "example_input": "Reschedule gym session to 6:30PM starting Oct 20th",
        "output": {
            "operation": "UPDATE",
            "parameters": {
                "eventId": "abc123xyz",
                "start": {"dateTime": "2023-10-20T18:30:00+07:00", "timeZone": "Asia/Ho_Chi_Minh"},
                "end": {"dateTime": "2023-10-20T19:30:00+07:00", "timeZone": "Asia/Ho_Chi_Minh"}
            }
        }
    }
}, indent=2, ensure_ascii=False)}

5. CRITICAL REQUIREMENTS:
- Return ONLY valid JSON
- NO additional explanations
- Auto-calculate time for "tomorrow", "next week", etc.
- Validate time correctness

Process this request: "{user_query}"
"""

    return prompt