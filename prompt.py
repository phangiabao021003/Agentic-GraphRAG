
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
RAG_PROMPT = lambda query,context,history: f"""
You are a helpful AI assistant that is very good in asking questions from the user.
user will ask question as: {query}
you must give answer with detailed explanation with bullets, heading , subheading etc. based on the context and historical conversation only, not on any external information.
always rename the title ,headings, subheading in your answer but keep the meaning same.
you must follow this  very stricty , dont use anything else other than the given :
context: {context}
ONLY use relevant information with the query from the context to answer.
if no related information found just reply with "The document does not contain the information mentioned in the question"
answer:
"""
LLM_PROMPT=  lambda query, history:f"""You are a helpful AI assistant that improves search queries based on conversation context.
        Given the following conversation history and the user's latest query, your task is to use the conversation history as context to answer the query if the query mentions, refers to any previous messages in the conversation, or coreference resolution is required. 
        
        --- Conversation History ---
        {history}
        
        --- Current Query ---
        {query}
        --- Answer ---
"""