from qdrant_client.http.models import Filter, FieldCondition, MatchValue
from typing import List, Dict, Any, Optional
import logging
import spacy
from qdrant_client.http.models import Filter, FieldCondition, MatchValue
from keybert import KeyBERT
from pydantic import BaseModel, Field
from typing import List
import torch
torch.classes.__path__ = []
from langchain_qdrant import  QdrantVectorStore
from transformers import AutoTokenizer, AutoModelForSequenceClassification
from langchain_qdrant import RetrievalMode
import config

# Load mô hình spaCy và KeyBERT
nlp = spacy.load("en_core_web_sm")
kw_model = KeyBERT()
tokenizer = AutoTokenizer.from_pretrained("BAAI/bge-reranker-v2-m3")
reranker = AutoModelForSequenceClassification.from_pretrained("BAAI/bge-reranker-v2-m3")
reranker.eval()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
class Entities(BaseModel):
    """Danh sách tên thực thể + khái niệm + chủ đề."""
    names: List[str] = Field(..., description="All entities, concepts, and keywords extracted from the text.")

class DocSearchTool():
    _instance = None
    _initialized = False
    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            logger.info("Creating new DocSearchTool instance")
            cls._instance = super(DocSearchTool, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if not self._initialized:
            self.__class__._initialized = True
            logger.info("Initialized DocSearchTool")

    def extract_entities(text: str) -> Entities: 
        doc = nlp(text)
        ner_entities = {ent.text.strip() for ent in doc.ents}
        noun_chunks = {chunk.text.strip() for chunk in doc.noun_chunks}
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
        entities = DocSearchTool.extract_entities(question)
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
    def rerank(query, docs, model, tokenizer, top_k=3):
        pairs = [(query, doc.page_content) for doc in docs]
        with torch.no_grad():
            inputs = tokenizer(pairs, padding=True, truncation=True, return_tensors='pt', max_length=512)
            scores = model(**inputs, return_dict=True).logits.view(-1, ).float()

        scored_docs = list(zip(docs, scores.tolist()))
        reranked = sorted(scored_docs, key=lambda x: x[1], reverse=True)
        return [doc for doc, score in reranked[:top_k]]

    async def full_retriever(graph, vector_store: QdrantVectorStore, question: str,doc_ids: list):
        graph_data = DocSearchTool.graph_retriever(question, graph)
        if doc_ids:
            filters = [
                FieldCondition(key="metadata.doc_id", match=MatchValue(value=doc_id))
                for doc_id in doc_ids
            ]
            final_filter = Filter(must=filters)
        else:
            final_filter = None  
        vector_data = vector_store.similarity_search(question, k=7, filter=final_filter)
        reranked_docs = DocSearchTool.rerank(question, vector_data, reranker, tokenizer, top_k=3)

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
    
    async def _run_tool(self, 
                        original_question: str, 
                        top_k: int,
                        doc_ids: list) -> str:
        try:


            # Get relevant documents pipeline
            relevant_docs = await self.full_retriever(
                query=original_question,
                top_k=top_k,
                doc_ids=doc_ids
            )      
            if not relevant_docs:
                return {
                    "success": True,
                    "content": f"No relevant documents found for query: '{original_question}'"
                }
            else:
                return relevant_docs      
                   
        except Exception as e:
            logger.error(f"docsearch query error: {str(e)}")
            return {
                "success": False,
                "content": f"Error during document search: {str(e)}"
            }
