from langchain_neo4j import Neo4jGraph
from neo4j import GraphDatabase
import os
import pickle
from dotenv import load_dotenv
load_dotenv()
class GraphDBConnection:
    def __init__(
        self,
        uri,
        username,
        password,
        database
    ):
        self.uri = uri
        self.username = username
        self.password = password
        self.database = database
        self.graph = None
        self.vector_retriever = None
        self.driver = GraphDatabase.driver(
            uri=self.uri,
            auth=(self.username, self.password)
        )

    def connect_to_graph(self) -> Neo4jGraph:
        try:
            self.graph = Neo4jGraph(
                url=self.uri,
                username=self.username,
                password=self.password,
                database=self.database
            )
            return self.graph
        except Exception as e:
            raise e

    def check_index_exists(self, tx):
        query = '''
        SHOW INDEXES YIELD name, type 
        WHERE type = "FULLTEXT" AND name = "fulltext_entity_id"
        RETURN count(*) AS index_count
        '''
        result = tx.run(query).single()
        return result["index_count"] > 0

    def create_fulltext_index(self, tx):
        query = '''
        CREATE FULLTEXT INDEX fulltext_entity_id 
        FOR (n:__Entity__) 
        ON EACH [n.id];
        '''
        tx.run(query)

    def setup_index(self):
        """
        Kiểm tra và tạo chỉ mục fulltext nếu cần.
        """
        with self.driver.session(database=self.database) as session:
            index_exists = session.execute_read(self.check_index_exists)
            if index_exists:
                print(f"✅ Index 'fulltext_entity_id' đã tồn tại trong database '{self.database}'.")

            else:
                session.execute_write(self.create_fulltext_index)
                print(f"✅ Index 'fulltext_entity_id' được tạo trong database '{self.database}'.")

    def close(self):
        self.driver.close()
if __name__ == "__main__":
    password = os.environ.get("NEO4J_PASSWORD")
    graph_conn = GraphDBConnection(
    uri="bolt://localhost:7687",
    username="neo4j",
    password=password,
    database="graduation")
    graph = graph_conn.connect_to_graph()
    
    with open("C:/Users/bao.phangia/Downloads/Đồ án/graph_documents_nutrition.pkl", "rb") as f:
        graph_documents = pickle.load(f)
        graph.add_graph_documents(
        graph_documents,
        baseEntityLabel=True,
        include_source=True)
