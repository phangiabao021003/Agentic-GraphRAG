import spacy
from qdrant_client.http.models import Filter, FieldCondition, MatchValue
from keybert import KeyBERT
from pydantic import BaseModel, Field
from typing import List
import torch
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
torch.classes.__path__ = []
from langchain_qdrant import  QdrantVectorStore
from transformers import AutoTokenizer, AutoModelForSequenceClassification
import logging
from selenium.webdriver.common.by import By
# Load mô hình spaCy và KeyBERT
nlp = spacy.load("en_core_web_sm")
kw_model = KeyBERT()
tokenizer = AutoTokenizer.from_pretrained("BAAI/bge-reranker-v2-m3")
reranker = AutoModelForSequenceClassification.from_pretrained("BAAI/bge-reranker-v2-m3")
reranker.eval()

class Entities(BaseModel):
    """Danh sách tên thực thể + khái niệm + chủ đề."""
    names: List[str] = Field(..., description="All entities, concepts, and keywords extracted from the text.")

def extract_entities(text: str) -> Entities: 
    doc = nlp(text)

    # Lấy thực thể NER
    ner_entities = {ent.text.strip() for ent in doc.ents}

    # Lấy noun chunks (cụm danh từ)
    noun_chunks = {chunk.text.strip() for chunk in doc.noun_chunks}

    # Lấy từ khóa bằng KeyBERT
    keywords = {kw[0].strip() for kw in kw_model.extract_keywords(text, stop_words='english', top_n=5)}

    # Gộp tất cả vào một tập hợp duy nhất
    combined = ner_entities.union(noun_chunks).union(keywords)

    return Entities(names=list(combined))

# Fulltext index query
def graph_retriever(question, graph) -> str:
    """
    Collects the neighborhood of entities mentioned
    in the question
    """
    result = ""
    entities = extract_entities(question)
    for entity in entities.names:
        response = graph.query(
            """CALL db.index.fulltext.queryNodes('fulltext_entity_id', $query, {limit:2})
            YIELD node,score
            CALL {
              WITH node
              MATCH (node)-[r:!MENTIONS]->(neighbor)
              RETURN node.id + ' - ' + type(r) + ' -> ' + neighbor.id AS output
              UNION ALL
              WITH node
              MATCH (node)<-[r:!MENTIONS]-(neighbor)
              RETURN neighbor.id + ' - ' + type(r) + ' -> ' +  node.id AS output
            }
            RETURN output LIMIT 50
            """,
            {"query": entity},
        )
        result += "\n".join([el['output'] for el in response])
    return result
def rerank(query, docs, model, tokenizer, top_k=4):
    pairs = [(query, doc.page_content) for doc in docs]
    with torch.no_grad():
        inputs = tokenizer(pairs, padding=True, truncation=True, return_tensors='pt', max_length=512)
        scores = model(**inputs, return_dict=True).logits.view(-1, ).float()

    scored_docs = list(zip(docs, scores.tolist()))
    reranked = sorted(scored_docs, key=lambda x: x[1], reverse=True)
    return [doc for doc, score in reranked[:top_k]]

def full_retriever( vector_store: QdrantVectorStore, question: str,doc_ids: list):
    # graph_data = graph_retriever(question, graph)
    if doc_ids:
        filters = [
            FieldCondition(key="metadata.doc_id", match=MatchValue(value=doc_id))
            for doc_id in doc_ids
        ]
        final_filter = Filter(must=filters)
    else:
        final_filter = None  
    vector_data = vector_store.similarity_search(question, k=7, filter=final_filter)
    reranked_docs = rerank(question, vector_data, reranker, tokenizer, top_k=3)

    cleaned_contents = []
    for idx, doc in enumerate(reranked_docs, start=1):
        content = doc.page_content.replace("\n", " ")
        cleaned_contents.append(f"{idx}. {content}")

    joined_contents = "\n".join(cleaned_contents)
    
    # final_data = f"""
    # ##
    # Graph data:
    # {graph_data}
    # ##    
    # Vector data:
    # {joined_contents}"""
    
    return joined_contents
def web_searching(driver,query: str, max_links: int = 5, max_contents: int = 2 ):
    """
    Perform a web search and retrieve page content using a single Chrome driver instance.

    Args:
        query (str): The search query.
        max_links (int): Maximum number of links to fetch from search results.
        max_contents (int): Maximum number of page contents to retrieve.

    Returns:
        str: Combined content from the fetched web pages.
    """
    results_web_searching = []
    # driver = None
    text_web_searching = ""  # Initialize the variable here

    try:
        # Initialize the Chrome driver once
        # driver = chrome()
        # Remove implicit wait to avoid conflicts with explicit waits
        wait = WebDriverWait(driver, 10)  # Explicit wait

        # Step 1: Fetch links from Google search results
        search_url = f"https://www.google.com/search?q={query}"
        driver.get(search_url)
        logging.info(f"Navigated to search URL: {search_url}")

        # Wait for search results to load using CSS selector
        wait.until(
            EC.presence_of_all_elements_located((By.CSS_SELECTOR, 'a[jsname="UWckNb"]'))
        )
        link_elements = driver.find_elements(By.CSS_SELECTOR, 'a[jsname="UWckNb"]')
        links = []

        for link_element in link_elements[:max_links]:
            href = link_element.get_attribute("href")
            if href:
                links.append(href)
                logging.info(f"Link found: {href}")

        # Step 2: Iterate through the fetched links and get page content
        bad_domains = ["youtube.com"]
        for link in links:
            if any(bad_domain in link for bad_domain in bad_domains):
                logging.info(f"Skipping unwanted domain: {link}")
                continue

            try:
                driver.get(link)
                logging.info(f"Navigated to URL: {link}")

                # Wait for the body of the page to load
                wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
                content = driver.find_element(By.TAG_NAME, "body").text
                if content:
                    results_web_searching.append(content)
                    logging.info(f"Content fetched from {link}")
            except Exception as e:
                logging.warning(f"Error fetching content from {link}: {e}")
                continue

            if len(results_web_searching) >= max_contents:
                logging.info(f"Reached maximum content limit: {max_contents}")
                break

        # Step 3: Combine the fetched contents
        text_web_searching = "\n\n".join(
            [f'- "{content}"' for content in results_web_searching]
        )
        text_web_searching = text_web_searching[:20000]  # Limit to 20,000 characters
        logging.info("Web searching completed successfully.")

    except Exception as general_e:
        logging.error(f"An unexpected error occurred: {general_e}")
        # Optionally, set text_web_searching to an error message or keep it as initialized

    # finally:
    #     if driver:
    #         driver.quit()  # Ensure the driver is properly closed
    #         logging.info("Chrome driver has been closed.")

    return text_web_searching
def chrome():
    # Configure Chrome options
    options = Options()
    # options.add_argument("--headless=new")  # Use the new headless mode
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-plugins")
    options.add_argument("--disable-popup-blocking")
    options.add_argument("--disable-translate")
    options.add_argument("--ignore-certificate-errors")
    options.add_argument("--allow-insecure-localhost")
    options.add_argument(
        "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/91.0.4472.124 Safari/537.36"
    )
    service = Service("/usr/local/bin/chromedriver")

    # Initialize the WebDriver with the specified service and options
    driver = webdriver.Chrome(service=service, options=options)
    return driver