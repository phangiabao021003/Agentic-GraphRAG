import aiohttp
import logging
import config
from typing import Dict, Any

logger = logging.getLogger(__name__)


class GoogleTool:
    """Google search tool using SerpAPI"""
    _instance = None
    _initialized = False

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            logger.info("Creating new GoogleTool instance")
            cls._instance = super(GoogleTool, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        self.name = "google"
        self.description = "A search engine retrieving top search results as snippets from Google. Input should be a search query."
    
    def search(self, query: str, max_results: int = 3) -> Dict[str, Any]:
        """Search Google for information"""
        try:
            api_key = getattr(config, "SERPAPI_API_KEY", None)
            if not api_key:
                return {
                    "success": False,
                    "error": "SerpAPI API key is missing in config.",
                    "content": ""
                }

            search_url = "https://serpapi.com/search"
            params = {
                "q": query,
                "api_key": api_key,
                "engine": "google",
                "num": max_results
            }

            with aiohttp.ClientSession() as session:
                with session.get(search_url, params=params) as response:
                    if response.status != 200:
                        return {
                            "success": False,
                            "error": f"SerpAPI request failed with status {response.status}",
                            "content": ""
                        }

                    data =  response.json()
                    organic_results = data.get("organic_results", [])[:max_results]

                    if not organic_results:
                        return {
                            "success": True,
                            "content": f"No results found for Google query: '{query}'",
                            "results": []
                        }

                    results = []
                    content_parts = []
                    for i, result in enumerate(organic_results, 1):
                        title = result.get("title", "No title")
                        link = result.get("link", "")
                        snippet = result.get("snippet", "No snippet")

                        results.append({
                            "title": title,
                            "url": link,
                            "snippet": snippet
                        })

                        content_parts.append(
                            f"Result {i}:\n"
                            f"Title: {title}\n"
                            f"URL: {link}\n"
                            f"Snippet: {snippet}\n"
                        )

                    return {
                        "success": True,
                        "content": "\n".join(content_parts),
                        "results": results
                    }

        except Exception as e:
            logger.error(f"Google search error: {str(e)}")
            return {
                "success": False,
                "error": f"Error during Google search: {str(e)}",
                "content": f"Google search failed: {str(e)}"
            }