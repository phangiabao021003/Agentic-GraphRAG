import datetime
import pytz
import json


# Prompt để tìm đoạn hội thoại liên quan nhất từ các đoạn trong lịch sử

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
enhancing_prompt="""You are a helpful AI assistant that is very good in explaining and expressing answer.
you must give answer with detailed explanation based on the CONTEXT as possible.
Give yourself room to think by extracting relevant passages from the context than use them to answer the query.
Don't return the thinking, only return the answer.
USING RELEVANT PASSAGES to answer the question.
If no relevant information found from CONTEXT or not provided CONTEXT just reply with "The document in database does not contain the information mentioned in the question."
ONLY RETURN THE FINAL ANSWER
THE FINAL ANSWER must be in {language}.
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
llm_prompt="""You are a helpful AI assistant that is very good in explaining and expressing answer.
you must give answer with detailed explanation with bullets, heading , subheading etc. based on the CONTEXT.
always rename the title ,headings, subheading in your answer but keep the meaning same.
make sure your answers are as explanatory as possible.
The answer must be in {language}.
###
QUERY: 
{query}
###
ANSWER:
"""
web_search_prompt="""You are a helpful AI assistant that is very good in answering user query based on PROVIDED INFORMATION from the web.
You must give answer with detailed explanation based on the PROVIDED INFORMATION as possible.
If no information in the PROVIDED INFORMATION relates to the question, respond with "The document does not contain the information mentioned in the question".
"""
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
    "recurrence": ["RRULE:FREQ=WEEKLY|MONTHLY...,UNTIL=string"],

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
- JSON MUST be ISO 8601 compliant

Process this request: "{user_query}"
"""

    return prompt

def process_json_ouput(json_input):
    prompt=f"""
You are a virtual assistant whose job is to convert Google Calendar data from JSON format into understandable schedule descriptions.{json_input}
The input json format structured as the example below: 
###The input JSON format is as follows:

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
      "recurrence": ["RRULE:FREQ=WEEKLY|MONTHLY...;UNTIL=string"],

      // READ (query)
      "timeMin": string,
      "timeMax": string,
      "q": string,

      // UPDATE/DELETE
      "eventId": string
    }},
    "metadata": {{
      "createdAt": string,
      "timezone": "Asia/Ho_Chi_Minh",
      "defaultReminders": [{{"method": "popup", "minutes": 10}}]
    }}
  }}
]

---

###Example input JSON:

[   "operation": "CREATE",
    "parameters": {{
      "summary": "Development Team Meeting",
      "description": "Discuss next sprint plan",
      "start": {{"dateTime": "2025-06-10T09:00:00+07:00", "timeZone": "Asia/Ho_Chi_Minh"}},
      "end": {{"dateTime": "2025-06-10T10:30:00+07:00", "timeZone": "Asia/Ho_Chi_Minh"}},
      "location": "Main Conference Room",
      "attendees": [
        {{"email": "nguyen.van.a@example.com", "displayName": "Nguyen Van A"}},
        {{"email": "le.thi.b@example.com", "displayName": "Le Thi B"}}
      ],
      "colorId": 5,
      "recurrence": ["RRULE:FREQ=WEEKLY;BYDAY=TU";UNTIL=2025-06-29T18:30:00+07:00]
    }},
    "metadata": {{
      "createdAt": "2025-05-25T15:00:00+07:00",
      "timezone": "Asia/Ho_Chi_Minh",
      "defaultReminders": [{{"method": "popup", "minutes": 10}}]
    }},
  {{
    "operation": "CREATE",
    "parameters": {{
      "summary": "Meeting with Client XYZ",
      "description": "",
      "start": {{"dateTime": "2025-06-12T14:00:00+07:00", "timeZone": "Asia/Ho_Chi_Minh"}},
      "end": {{"dateTime": "2025-06-12T15:00:00+07:00", "timeZone": "Asia/Ho_Chi_Minh"}},
      "location": "ABC Hotel",
      "attendees": [],
      "colorId": 3
    }},
    "metadata": {{
      "createdAt": "2025-05-26T10:00:00+07:00",
      "timezone": "Asia/Ho_Chi_Minh",
      "defaultReminders": [{{"method": "popup", "minutes": 15}}]
    }}
  }}
]

---

###Example output from json (If a field has no data (for example, location is missing), you can omit that part of the description):

- On June 10, 2025, from 09:00 to 10:30: Development Team Meeting at Main Conference Room. Attendees: Nguyen Van A, Le Thi B. Description: Discuss next sprint plan. This event recurs weekly on Tuesdays.

- On June 12, 2025, from 14:00 to 15:00: Meeting with Client XYZ at ABC Hotel.

---
Now, here is the input JSON, let's return the corresponding schedule description (ONLY return schedule description without any explainations): 
###JSON: "{json_input}" 
###Schedule description:"""
    return prompt

react_prompt="""Answer the following questions as best you can. You must give answer in {lang}. You have access to the following tools:
{tool_description}
Use the following format, ##Thought field is require:

##Thought: you should always think about what to do

##Action: the action to take, should be one of [{tool_names}]

##Action Input: the input to the action, should be different from the action input of the same action in previous steps.

Observation: the result of the action

... (this Thought/Action/Action Input/Observation can repeat N times)

##Thought: I now know the final answer
##Final Answer: the final answer to the original input question

Begin! After each Action Input.

Question: {question}
Thought:{agent_scratchpad}
"""