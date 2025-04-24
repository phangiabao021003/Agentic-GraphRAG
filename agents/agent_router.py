import requests
def classify_user_input(input: str) -> str:
    prompt = f"""
    Classify the topic of the input into one of the following categories:
    - 'llm' if it's a casual conversation, the questions aren't related to nutrition, RAG system of chatbot\n
    - 'rag' if it's a question about nutrition or when the user mentions to use RAG system\n
    - 'schedule' if it's about creating a health schedule

    The input: "{input}"
    The classification should be one of the following: llm / rag / schedule
    Do not provide any other response.
    """
    response = requests.post(
        "http://localhost:11434/v1/chat/completions",
        headers={"Content-Type": "application/json"},
        json={
            "model": "llama3.1",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0,
        }
    )
    result = response.json()
    return result["choices"][0]["message"]["content"].strip().lower()
