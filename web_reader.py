import requests
from bs4 import BeautifulSoup
import logging
from typing import Dict

logger = logging.getLogger(__name__)

class WebReaderTool:
    """Tool to fetch and extract readable content from a given web URL."""
    _instance = None
    _initialized = False

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            logger.info("Creating new WebReaderTool instance")
            cls._instance = super(WebReaderTool, cls).__new__(cls)
        return cls._instance

    def __init__(self, max_length: int = 3000):
        self.max_length = max_length

    def read_url(self, url: str) -> Dict[str, str]:
        try:
            # ✅ Làm sạch URL trước khi sử dụng
            clean_url = url.strip().strip('"').strip("'")

            # Sử dụng requests thay vì aiohttp
            response = requests.get(clean_url, timeout=10)
            
            if response.status_code != 200:
                return {
                    "success": False,
                    "error": f"Failed to fetch page. Status code: {response.status_code}",
                    "content": ""
                }

            html = response.text
            soup = BeautifulSoup(html, "html.parser")

            body = soup.body
            if not body:
                return {
                    "success": False,
                    "error": "No <body> tag found in HTML.",
                    "content": ""
                }

            text = body.get_text(separator="\n", strip=True)
            return {
                "success": True,
                "content": text[:self.max_length],
                "error": ""
            }

        except Exception as e:
            logger.error(f'Web reading error for URL "{url}": {str(e)}')
            return {
                "success": False,
                "error": f"Error reading URL: {str(e)}",
                "content": ""
            } 