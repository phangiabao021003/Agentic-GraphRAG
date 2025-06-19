import config
from dotenv import load_dotenv
import os
from serpapi import GoogleSearch
# Nạp biến môi trường từ tệp .env
load_dotenv()

# Lấy giá trị biến SERPAPI_API_KEY từ môi trường
api_key = os.getenv("SERPAPI_API_KEY")

def seach_web(query:str,api_key:str, max_results=3) -> list:
    params = {
            "q": query,
            "api_key": api_key,
            "engine": "google",
            "num": max_results
            }

    search = GoogleSearch(params)
    results = search.get_dict()

    # Lấy các kết quả hữu cơ (organic results)
    organic_results = results.get("organic_results", [])[:max_results]

    # Lấy ra chỉ các liên kết (links) từ các kết quả
    links = [result['link'] for result in organic_results]

    return links
