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

def router_output(output: str) -> str:
    prompt = f"""
    Based on the input, determine the input and classify it into one of the following categories:
    - 'schedule' if the input is about schedule.
    - 'normal' if the input is otherwise.
    The input: "{output}"
    The classification should be one of the following: schedule / normal 
    DO NOT provide any other response.
    """
    
    # Send POST request to the local server
    response = requests.post(
        "http://localhost:11434/v1/chat/completions",
        headers={"Content-Type": "application/json"},
        json={
            "model": "llama3.1",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0,
        }
    )
    # Check if request was successful
    response.raise_for_status()  # Raises HTTPError for bad responses (4xx and 5xx)
    
    # Process the response
    result = response.json().get("choices", [{}])[0].get("message", {}).get("content", "").strip().upper()
    
    # Return True if the classification is "schedule", False otherwise
    return "SCHEDULE" in result