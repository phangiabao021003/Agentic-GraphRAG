import datetime
import pytz
import json


# Prompt để tìm đoạn hội thoại liên quan nhất từ các đoạn trong lịch sử
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
  • Time (start and end)
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
[{{
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
- RETURN ONLY VALID JSON ARRAY (NO TEXT, NO MARKDOWN, NO COMMENTS)
- NO additional explanations
- Auto-calculate time for "tomorrow", "next week", etc.
- Validate time correctness

Process this request: "{user_query}"
"""

    return prompt

def process_calendar_query(query):
    prompt=f"""
You are an intelligent assistant specializing in schedule management. Analyze USER QUERY and classify them into the following types:
- TYPE 1: User requests the assistant to create a schedule based on a general description.
- TYPE 2: User provides specific details to create, update, edit, or delete a schedule, including time and activities.
Instructions:
- For TYPE 1, OUTPUT_1: generate a schedule based on the user's description.
- For TYPE 2, OUTPUT_2: return the specific schedule details provided by the user.
###
USER QUERY: "{query}"
IMPORTANT: ONLY return the output — do not include the request type in the response.
"""
    return prompt
