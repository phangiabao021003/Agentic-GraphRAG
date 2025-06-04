import requests
def router_query(input: str) -> str:
    prompt = f"""
    Classify the topic of the input into one of the following categories:
    - 'llm' if the input is a casual conversation, like 'How are you?' or 'Tell me a joke.'
    - 'rag' if the user asks information nutrition, health, diet, or any question where the user mentions nutrition or RAG system.
    - 'calendar' if the input mentions to Create/Update/Read/Delete scheduling (IMPORTANT: Any query that refers to the schedule)

    The input: "{input}"
    The classification should be one of the following: llm / rag / calendar
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
