import asyncio
import logging
import json
import re
import aiohttp
import urllib.parse
from typing import List, Dict, Any, Optional, AsyncGenerator, Callable

import config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ReActPipeline:
    """
    ReAct (Reasoning and Acting) Pipeline that combines reasoning with action execution
    Supports tools: Wikipedia, Google Search, and LLM calls
    """
    
    def __init__(
        self,
        vectordb: VectorDBEngine,
    ):
        self.max_iterations = config.DEFAULT_MAX_REACT_ITERATIONS
        self.tool_registry = ToolRegistry(vectordb_engine)
        
        # Initialize AI client
        self.llm_client = ai.Client()
           
        # Reflection engine for reasoning
        self.reflection_engine = ReflectionEngine(self.llm_client)

    async def _execute_action(self, action: str, action_input: str, llm_setting:Optional[LLMSettings]=None, docsearch_setting: Optional[Any]=None) -> dict:
        """Execute a tool action and return the observation"""
        return await self.tool_registry.execute_tool_action(action, action_input, llm_setting, docsearch_setting)     

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

    async def stream_completion(
            self,
            provider_name: str,
            model_name: str,
            messages: List[Dict[str, str]],
            callback: Optional[Callable[[str], None]] = None,
            **kwargs
    ) -> AsyncGenerator[str, None]:
        # Create a streaming request to OpenAI
        stream = await asyncio.to_thread(
            self.llm_client.chat.completions.create,
            model=f"{provider_name}:{model_name}",
            messages=messages,
            **kwargs
        )

        collected_message = ""

        for chunk in stream:
            if chunk.choices and len(chunk.choices) > 0:
                content = chunk.choices[0].delta.content
                if content:
                    collected_message += content
                    if callback:
                        callback(content)
                    yield content
                    await asyncio.sleep(0.01)
            else:
                yield chunk.usage

    async def stream(
        self, original_question: str,
        messages: List[Dict[str, str]], 
        chat_history: List[Dict[str, str]], 
        n_last_interactions: int,
        max_context_rewrite_length: int,
        collection_id: str,
        tenant_id: str,
        user_group_id: str,
        top_k: int,
        qa_prompt: str
    ) -> AsyncGenerator[str, None]:
        """Stream ReAct response with reasoning and actions"""
        agent_tools =  ["docsearch", "llm"]
        language = 'English'
        
        tools = ", ".join(agent_tools)

        max_iterations = self.max_iterations
        conversation_log = []
        completion_tokens = 0
        prompt_tokens = 0
        total_tokens = 0
        iteration = 0

        while iteration < max_iterations:
            iteration += 1
            try:
                agent_scratchpad = self._construct_scratchpad(conversation_log=conversation_log)
                prompt = qa_prompt or config.react_prompt.format(tool_description=self.tool_registry.get_tool_descriptions(tool_name_setting=agent_tools),
                                                                tool_names=tools,
                                                                question=original_question,
                                                                agent_scratchpad=agent_scratchpad,
                                                                lang=language)
                messages.extend([{"role": "user", "content": prompt}])

                llm_response = ""
                async for chunk in self.stream_completion(provider_name, model_name, messages, stop=["Observation:"], stream=True, stream_options={
                    "include_usage": True
                }):
                        llm_response += chunk

                parsed = self._parse_react_response(llm_response)

                if 'final_answer' in parsed.keys() or "Final Answer:" in llm_response:
                    final_answer = parsed.get('final_answer') or llm_response.split("Final Answer:")[-1].strip()

                    yield "data: " + json.dumps({
                        "type": "token",
                        "content": final_answer
                    }) + "\n\n"
                    break

                if 'action' in parsed.keys() and 'action_input' in parsed.keys():
                    action = parsed['action']
                    action_input = parsed['action_input']

                    yield "data: " + json.dumps({
                        "type": "action",
                        "action": action,
                        "input": action_input
                    }) + "\n\n"

                    observation = await self._execute_action(
                        action,
                        action_input,
                        reasoning_settings.llm,
                        {
                            "original_question": original_question,
                            "chat_history": chat_history,
                            "n_last_interactions": n_last_interactions,
                            "max_context_rewrite_length": max_context_rewrite_length,
                            "top_k": top_k,
                            "collection_id": collection_id,
                            "tenant_id": tenant_id,
                            "user_group_id": user_group_id,
                            "retrieval_settings": retrieval_settings,
                            "reasoning_settings": reasoning_settings
                        }
                    )
                    if "usage" in observation.keys():
                        completion_tokens += observation["usage"]["completion_tokens"]
                        prompt_tokens += observation["usage"]["prompt_tokens"]
                        total_tokens += observation["usage"]["total_tokens"]
                        
                    yield "data: " + json.dumps({
                        "type": "observation",
                        "content": f"\n\nObservation:\n {observation['content']}\n\n"
                    }) + "\n\n"

                    conversation_log.append({
                        "iteration": iteration,
                        "log": parsed["thought"] + f"""
                            Action: {action}
                            Action Input: {action_input}
                        """,
                        "observation": observation['content']
                    })
                else:
                    yield "data: " + json.dumps({
                        "type": "error",
                        "message": "No valid action found in LLM response"
                    }) + "\n\n"
                    break

            except Exception as e:
                logger.error(f"Error in ReAct iteration {iteration}: {str(e)}")
                yield "data: " + json.dumps({
                    "type": "error",
                    "message": f"Error in iteration {iteration}: {str(e)}"
                }) + "\n\n"
                break

        if iteration >= max_iterations:
            yield "data: " + json.dumps({
                "type": "status",
                "message": "Reached maximum iterations. Providing best available answer..."
            }) + "\n\n"

            final_messages = messages + [
                {"role": "user", "content": "Please provide a Final Answer based on the information gathered so far."}
            ]

            async for chunk in self.stream_completion(provider_name, model_name, final_messages, stream=True, stream_options={
                    "include_usage": True
                }):
                if type(chunk) is str:
                    yield "data: " + json.dumps({
                        "type": "token",
                        "content": chunk
                    }) + "\n\n"
            else:
                    completion_tokens += chunk.completion_tokens
                    prompt_tokens += chunk.prompt_tokens
                    total_tokens += chunk.total_tokens
                    
        yield "data: " + json.dumps({
            "type": "done",
            "conversation_log": conversation_log
        }) + "\n\n"
        # Send completion usage
        
        yield "data: " + json.dumps({"type": "usage", "completion_tokens": completion_tokens, "prompt_tokens": prompt_tokens, "total_tokens": total_tokens}) + "\n\n" 