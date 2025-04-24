from typing import List
from openai import OpenAI
from difflib import SequenceMatcher
import time
import json
class ContextAwareAgent:
    def __init__(self, client, max_context_tokens=4000):
        self.client = client
        self.chat_history = []
        self.max_context_tokens = max_context_tokens

    def add_to_history(self, role, content):
        self.chat_history.append({"role": role, "content": content})
    def delete_history(self):
        self.chat_history = []
    def should_use_history(self, message: str) -> bool:
        prompt = f""" You are a conversational AI. The user has just asked the following question: "{message}". 
Please analyze the question to determine if it mentions or refers to any previous messages in the conversation, or if coreference resolution is required. 
Answer only "YES" if the query relates to or depends on past conversations, otherwise answer "NO".
"""
        response = self.client.chat.completions.create(
            model="llama3.1",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=2,
            temperature=0.1
        )
        result = response.choices[0].message.content
        print(f"Response: {result}")
        return "YES" in result.strip().upper()

    def sliding_window_chunks(self, window_size=2) -> List[str]:
        history = [f"{m['role'].capitalize()}: {m['content']}" for m in self.chat_history]
        # return ["\n".join(history[i:i+window_size]) for i in range(len(history) - window_size + 1)]
        return ["\n".join(history[-4:])] if len(history) >= window_size else history
    # def fuzzy_match_score(self, a: str, b: str) -> float:
    #     return SequenceMatcher(None, a.lower(), b.lower()).ratio()
    def rewrite_query(self, user_message: str, chunks: List[str]) -> str:
        his_con = "\n-".join(chunks)
        prompt = f"""Rewrite the following query based on relevant context from the conversation history.
    The rewritten query should:
    - PRESERVE the core intent and meaning of the original query
    - Clarify the query to make it more specific and informative for retrieving relevant context
    - Avoid introducing new topics or queries that deviate from the original query
    - DONT EVER ANSWER the Original query, but instead focus on rephrasing and expanding it into a new query
    Return ONLY the rewritten query text if needed, without any additional formatting or explanations; otherwise, return original query.

    Conversation History: {his_con}
    Original query: {user_message}

    Rewritten query:
        """
        response = self.client.chat.completions.create(
            model='llama3.2',
            messages=[{"role": "user", "content": prompt}],
            max_tokens=256,
            temperature=0,
        )
        rewritten_query = response.choices[0].message.content.strip()

        return rewritten_query

#     def rank_chunks(self, current_message: str, chunks: List[str]) -> str:
#         chunks = "\n-".join(chunks)
#         prompt = f""" 
# You are a conversational AI. The user just said: "{current_message}"
# which one of these conversation is the most relevant with the query of user.
# The conversation history is:{chunks}
# Return ONLY the most relevant conversation with current message without any additional formatting or explanations.
# If there is no relevant conversation, return "NO RELEVANT CONVERSATION".
# """
#         response = self.client.chat.completions.create(
#             model="llama3.1",
#             messages=[{"role": "user", "content": prompt}],
#             max_tokens=256,
#             stream=True,
#             temperature=0.1
#         )
#         collected_message = ""
#         for chunk in response:
#             if chunk.choices and len(chunk.choices) > 0:
#                 content = chunk.choices[0].delta.content or ""
#                 if content:
#                     print(content, end="", flush=True)  # In ngay ra console
#                     collected_message += content
#                     time.sleep(0.01)
#         return collected_message.strip()
        # for chunk in chunks:
        #     if self.fuzzy_match_score(current_message, chunk) > 0.5:
        #         return chunk
        # ranked = []
        # for chunk in chunks:
        #     score = self.fuzzy_match_score(current_message, chunk)
        #     ranked.append((score, chunk))

        # ranked.sort(reverse=True, key=lambda x: x[0])
        # return ranked[0][1] if ranked else ""

    # def get_tokens(self, text: str) -> int:
    #     enc = tiktoken.get_encoding("cl100k_base")
    #     return len(enc.encode(text))

    #     if self.get_tokens(full_prompt) > self.max_context_tokens:
    #         return user_message  # fallback nếu quá dài
    #     return full_prompt

    def generate_reply(self, user_message: str) -> str:
        
        # use_history = self.should_use_history(user_message)
        # if not use_history or len(self.chat_history) < 2:
        #     print("Not using user message for query rewriting.")
        #     new_query = user_message
        # else:
        #     print("Using history for query rewriting.")
        chunks = self.sliding_window_chunks()
        print(f"Chunks: {chunks}")
        new_query = self.rewrite_query(user_message, chunks)
        # relevant_history = self.rank_chunks(user_message, chunks)
        return new_query #relevant_history
    