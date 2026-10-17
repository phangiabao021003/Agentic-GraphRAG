import logging

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

FALLBACK_MESSAGE = "Không thể tìm thấy kết quả tìm kiếm liên quan"
SERPAPI_URL = "https://serpapi.com/search"
PAGE_CHAR_LIMIT = 1000
REQUEST_TIMEOUT = 10


def _search_links(query: str, api_key: str, max_results: int) -> list[str]:
    response = requests.get(
        SERPAPI_URL,
        params={"q": query, "api_key": api_key, "engine": "google", "num": max_results},
        timeout=REQUEST_TIMEOUT,
    )
    response.raise_for_status()
    organic_results = response.json().get("organic_results", [])[:max_results]
    return [result["link"] for result in organic_results if "link" in result]


def _read_page(url: str) -> str:
    response = requests.get(url, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    soup = BeautifulSoup(response.content, "html.parser")
    return soup.get_text(separator=" ", strip=True)[:PAGE_CHAR_LIMIT]


def web_search(query: str, api_key: str, max_results: int = 3) -> str:
    try:
        links = _search_links(query, api_key, max_results)
        if not links:
            return FALLBACK_MESSAGE

        pages = []
        for link in links:
            try:
                text = _read_page(link)
                if text:
                    pages.append(f"{link}\n{text}")
            except Exception:
                logger.exception("Failed to read page %s", link)

        if not pages:
            return FALLBACK_MESSAGE
        return "\n\n---\n\n".join(pages)
    except Exception:
        logger.exception("web_search failed for query=%r", query)
        return FALLBACK_MESSAGE
