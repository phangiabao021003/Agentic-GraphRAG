import asyncio
import logging
import json
import re
import time

from typing import List, Dict, Any, Optional, AsyncGenerator, Callable
from search_agent.tools import ToolRegistry
import config
from openai import OpenAI
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
from langchain_qdrant import QdrantVectorStore

class ReActPipeline:
    """
    ReAct (Reasoning and Acting) Pipeline that combines reasoning with action execution
    Supports tools: Wikipedia, Google Search, and LLM calls
    """
    
    def __init__(self, 
                 vector_store: QdrantVectorStore,
                 client: OpenAI):
        self.max_iterations = 3
        self.tool_registry = ToolRegistry(vector_store=vector_store)
        self.client = client
        # Reflection engine for reasoning

    def _execute_action(self, action: str, action_input: str, docsearch_setting: Optional[Any]=None) -> dict:
        """Execute a tool action and return the observation"""
        return self.tool_registry.execute_tool_action(action, action_input,  docsearch_setting)     

    def _parse_react_response(self, response: str) -> Dict[str, str]:
        """Parse ReAct response to extract thought, action, and action input"""
        result = {}
        
        # Extract Thought
        thought_match = re.search(r'##Thought:\s*(.*?)(?=\n(?:##Action|##Final Answer)|$)', response, re.DOTALL | re.IGNORECASE)
        if thought_match:
            result['thought'] = thought_match.group(1).strip()
        
        # Extract Action
        action_match = re.search(r'##Action\s*\d*\s*:[\s]*(.*?)[\s]*##Action\s*\d*\s*Input\s*\d*\s*:[\s]*(.*)', response, re.IGNORECASE)
        if action_match:
            action = action_match.group(1).strip()
            result['action'] = action
        
        # Extract Action Input
        action_input_match = re.search(r'##Action Input:\s*(.*?)(?=\n|$)', response, re.DOTALL | re.IGNORECASE)
        if action_input_match:
            result['action_input'] = action_input_match.group(1).strip()
        
        # Extract Final Answer
        final_answer_match = re.search(r'##Final Answer:\s*(.*)', response, re.DOTALL | re.IGNORECASE)
        if final_answer_match:
            result['final_answer'] = final_answer_match.group(1).strip()
        
        return result

    def _construct_scratchpad(
        self, conversation_log = []
    ) -> str:
        """Construct the scratchpad that lets the agent continue its thought process."""
        thoughts = ""
        for step in conversation_log:
            thoughts += step["log"] + "\n"
            thoughts += f"\nObservation: " + step["observation"] + "\nThought:"
        return thoughts

    def stream_completion(
            self,
            messages: List[Dict[str, str]],
            callback: Optional[Callable[[str], None]] = None,
            **kwargs
    ):
        response = self.client.chat.completions.create(
            model='llama3.2',
            messages=messages,
            max_tokens=2048,
            stream=True,
            temperature=0.5,
            **kwargs
        )
        collected_message = ""
        for chunk in response:
            if chunk.choices and len(chunk.choices) > 0:
                content = chunk.choices[0].delta.content or ""
                if content:
                    print(content, end="", flush=True)  # In ngay ra console
                    collected_message += content
                    time.sleep(0.01)  # Thêm độ trễ giữa các chunk để dễ đọc hơn
        return collected_message

    def stream(
        self, 
        original_question: str,
        messages: List[Dict[str, str]], 
        top_k: int,
        doc_ids:list
        ):
        """Stream ReAct response with reasoning and actions"""
        agent_tools =  ["docsearch", "llm"]
        language = 'English'
        
        tools = ", ".join(agent_tools)

        max_iterations = self.max_iterations
        conversation_log = []
        iteration = 0

        while iteration < max_iterations:
            iteration += 1
            try:
                agent_scratchpad = self._construct_scratchpad(conversation_log=conversation_log)
                prompt = config.react_prompt.format(tool_description=self.tool_registry.get_tool_descriptions(tool_name_setting=agent_tools),
                                                                tool_names=tools,
                                                                question=original_question,
                                                                agent_scratchpad=agent_scratchpad,
                                                                lang=language)
                messages.extend([{"role": "user", "content": prompt}])

                llm_response = self.stream_completion( messages, stop=["Observation:"], stream_options={
                    "include_usage": True
                })

                parsed = self._parse_react_response(llm_response)

                if 'final_answer' in parsed.keys() or "Final Answer:" in llm_response:
                    output = parsed.get('final_answer') or llm_response.split("Final Answer:")[-1].strip()
                    return output
                if 'action' in parsed.keys() and 'action_input' in parsed.keys():
                    action = parsed['action']
                    action_input = parsed['action_input']

                    observation = self._execute_action(
                        action,
                        action_input,
                        {
                            "original_question": original_question,
                            "doc_ids": doc_ids,
                        }
                    )
                    if "usage" in observation.keys():
                        completion_tokens += observation["usage"]["completion_tokens"]
                        prompt_tokens += observation["usage"]["prompt_tokens"]
                        total_tokens += observation["usage"]["total_tokens"]
                    conversation_log.append({
                        "iteration": iteration,
                        "log": parsed["thought"] + f"""
                            Action: {action}
                            Action Input: {action_input}
                        """,
                        "observation": observation['content']
                    })
                else:
                    output = "No valid action found in response. Please try again."


            except Exception as e:
                logger.error(f"Error in ReAct iteration {iteration}: {str(e)}")
                break

        if iteration >= max_iterations:
            final_messages = messages + [
                {"role": "user", "content": "Please provide a Final Answer based on the information gathered so far."}
            ]

            output = self.stream_completion( final_messages, 
                                            stream_options={"include_usage": True})
            return output