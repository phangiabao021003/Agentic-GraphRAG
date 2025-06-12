from typing import Any, Dict, List, Optional
from search_agent.doc_search import DocSearchTool
from search_agent.wikipedia import WikipediaTool
from search_agent.google import GoogleTool


class ToolRegistry:
    """Manages and orchestrates all available tools"""
    
    def __init__(self):
        self.wikipedia = WikipediaTool()
        self.google = GoogleTool()
        self.docsearch = DocSearchTool()

        # Tool definitions for LLM
        self.tool_definitions = {
            "wikipedia": {
                "name": "wikipedia",
                "description": self.wikipedia.description,
                "parameters": {
                    "query": "The search query to look up on Wikipedia"
                },
                "example": "wikipedia('Albert Einstein')"
            },
            "google": {
                "name": "google", 
                "description": self.google.description,
                "parameters": {
                    "query": "The search query to look up on Google"
                },
                "example": "google('latest AI research 2024')"
            },
            "docsearch": {
                "name": "docsearch",
                "description": "A storage that contains internal documents. If you lack any specific private information to answer the question, you can search in this document storage. Furthermore, if you are unsure about which document that the user refers to, likely the user already selects the target document in this document storage, you just need to do normal search. If possible, formulate the search query as specific as possible.",
                "parameters": {
                    "original_question": "question",
                    "chat_history": "history of chat",
                    "n_last_interactions": "",
                    "max_context_rewrite_length": "",
                    "top_k": "",
                    "collection_id": "",
                    "tenant_id": "",
                    "user_group_id": "",
                    "retrieval_settings": "",
                    "reasoning_settings": "",
                },
                "example": ""
            }
        }
    
    def get_tool_descriptions(self, tool_name_setting: Optional[List[str]] = None) -> str:
        """Get formatted descriptions of available tools"""
        if tool_name_setting is None:
            tool_name_setting = ['wikipedia', 'google']

        descriptions = []
        for tool_name in tool_name_setting:
            if tool_name in self.tool_definitions:
                tool_info = self.tool_definitions[tool_name]
                descriptions.append(f"- {tool_name}: {tool_info['description']}")
        
        return "\n".join(descriptions)
    
    async def execute_tool_action(self, action: str, action_input: str, docsearch_setting: Optional[Any]=None) -> dict:
        """Execute a tool action and return formatted result"""
        action = action.lower().strip()
        
        try:
            if action == "wikipedia":
                result = await self.wikipedia.search(query=action_input)
            elif action == "google":
                result = await self.google.search(query=action_input)
            elif action == "docsearch":
                result = await self.docsearch._run_tool(
                        original_question=docsearch_setting["original_question"],
                        top_k=docsearch_setting["top_k"],
                        doc_ids=docsearch_setting["doc_ids"]

                )
            else:
                result = {'success': False, 'content': f"Unknown action: {action}"}
            
            return result
                
        except Exception as e:
            return e