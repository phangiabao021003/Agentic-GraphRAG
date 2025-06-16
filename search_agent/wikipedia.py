import aiohttp
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


class WikipediaTool:
    """Wikipedia search tool"""
    _instance = None
    _initialized = False

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            logger.info("Creating new WikipediaTool instance")
            cls._instance = super(WikipediaTool, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        self.name = "wikipedia"
        self.description = "Search engine from Wikipedia, retrieving relevant wiki page. Useful when you need to get holistic knowledge about people, places, companies, historical events, or other subjects. Input should be a search query."
    
    def search(self, query: str, max_results: int = 1) -> Dict[str, Any]:
        """Search Wikipedia for information"""
        try:
            search_url = "https://en.wikipedia.org/w/api.php"
            
            # Search for pages
            search_params = {
                'action': 'query',
                'format': 'json',
                'list': 'search',
                'srsearch': query,
                'srlimit': max_results,
                'srprop': 'snippet|titlesnippet|size|timestamp'
            }
            
            with aiohttp.ClientSession() as session:
                with session.get(search_url, params=search_params) as response:
                    if response.status != 200:
                        return {
                            "success": False,
                            "error": f"Wikipedia API returned status {response.status}",
                            "content": ""
                        }
                    
                    data =  response.json()
                    search_results = data.get('query', {}).get('search', [])
                    
                    if not search_results:
                        return {
                            "success": True,
                            "content": f"No Wikipedia articles found for query: '{query}'",
                            "results": []
                        }
                    
                    # Get detailed information
                    results = []
                    for result in search_results:
                        page_title = result['title']
                        
                        extract_params = {
                            'action': 'query',
                            'format': 'json',
                            'prop': 'extracts|info',
                            'titles': page_title,
                            'exintro': '1',
                            'explaintext': '1',
                            'exsectionformat': 'plain',
                            'inprop': 'url'
                        }
                        
                        with session.get(search_url, params=extract_params) as extract_response:
                            if extract_response.status == 200:
                                extract_data =  extract_response.json()
                                pages = extract_data.get('query', {}).get('pages', {})
                                
                                for page_id, page_info in pages.items():
                                    if page_id != '-1':
                                        results.append({
                                            "title": page_info.get('title', 'Unknown'),
                                            "extract": page_info.get('extract', 'No extract available')[:1000],
                                            "url": page_info.get('fullurl', ''),
                                            "snippet": result.get('snippet', '')
                                        })
                    
                    if results:
                        content_parts = []
                        for i, result in enumerate(results, 1):
                            content_parts.append(
                                f"Result {i}:\n"
                                f"Title: {result['title']}\n"
                                f"URL: {result['url']}\n"
                                f"Content: {result['extract']}\n"
                            )
                        
                        return {
                            "success": True,
                            "content": "\n".join(content_parts),
                            "results": results
                        }
                    else:
                        return {
                            "success": True,
                            "content": f"Found search results but could not retrieve detailed content for query: '{query}'",
                            "results": []
                        }
                        
        except Exception as e:
            logger.error(f"Wikipedia search error: {str(e)}")
            return {
                "success": False,
                "error": f"Error searching Wikipedia: {str(e)}",
                "content": f"Wikipedia search failed: {str(e)}"
            }