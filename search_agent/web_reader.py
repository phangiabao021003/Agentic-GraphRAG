import aiohttp
from bs4 import BeautifulSoup
import logging
from typing import Dict
import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

def read_web(url: str, max_length: int = 1000):
        try:
            # ✅ Làm sạch URL trước khi sử dụng
            clean_url = url.strip().strip('"').strip("'")
            response = requests.get(url)
            if response.status_code != 200:
                logger.error(f'Failed to fetch URL "{url}". Status code: {response.status_code}')
                return "Error fetching URL: ", response.status_code
            else:    
                soup = BeautifulSoup(response.content, "html.parser")
                text = soup.get_text(separator="", strip=True)
            return text[:max_length]

        except Exception as e:
            logger.error(f'Web reading error for URL "{url}": {str(e)}')
            return e
