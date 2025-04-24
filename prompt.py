
CHECK_REFERENCE_PROMPT = lambda message: f"""
You are a conversational AI. The user just query: "{message}"
Based on the query, determine whether this query mentions, references, or requires the use of historical conversations.
Answer only: "YES" or "NO"
"""

# Prompt để tìm đoạn hội thoại liên quan nhất từ các đoạn trong lịch sử
RANK_HISTORY_PROMPT = lambda query, chunks: f"""
You are a conversational AI. The user just said: "{query}"
Which one of these conversation is the most relevant with the query of user?
The conversation history is:
{chunks}

Consider the most relevant conversation history as the context of the user query.
Answer the query based on this context as clearly as possible.
If the conversation history does not contain any information related to the user query, please answer with "Cannot find any information".
Answer:
"""

# Prompt dùng để quyết định dùng RAG hay không
RAG_ROUTER_PROMPT = lambda query: f"""
You are a routing agent. Decide whether this user query: "{query}"
requires retrieving external knowledge via RAG (Retrieval-Augmented Generation).
Answer only "RAG" if external information is needed or "NO_RAG" if not.
"""
base_prompt=  lambda query, context:f"""You are a helpful AI assistant that explains and expresses answer for anything asked by the user in English.
Given the following conversation history and the user's latest query, your task is to:
1. give answer with detailed explanation with bullets, heading , subheading etc. based on the context only, not on any external information.
2. always rename the title ,headings, subheading in your answer but keep the meaning same.
3. you must follow this  very stricty , don't use anything else other than the context
4. if no related information found just reply with "The document does not contain the information mentioned in the question"

IMPORTANT: ONLY use relevant information with the query from the context to answer.

--- Context ---
{context}
        
--- Current Query ---
{query}

Answer:
"""