import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from dotenv import load_dotenv
load_dotenv()

from neo4j import GraphDatabase
from neo4j_graphrag.generation import GraphRAG
# tag::import_text2cypher[]
from neo4j_graphrag.retrievers import Text2CypherRetriever
# end::import_text2cypher[]
from tools.llm_provider import create_neo4j_llm

# Connect to Neo4j database
driver = GraphDatabase.driver(
    os.getenv("NEO4J_URI"), 
    auth=(
        os.getenv("NEO4J_USERNAME"), 
        os.getenv("NEO4J_PASSWORD")
    )
)

# tag::t2c_llm[]
# Create Cypher LLM
t2c_llm = create_neo4j_llm(model_params={"temperature": 0})
# end::t2c_llm[]

# tag::retriever[]
# Build the retriever
retriever = Text2CypherRetriever(
    driver=driver,
    llm=t2c_llm,
)
# end::retriever[]

llm = create_neo4j_llm()
rag = GraphRAG(retriever=retriever, llm=llm)

query_text = "Which movies did Hugo Weaving acted in?"
query_text = "What are examples of Action movies?"

response = rag.search(
    query_text=query_text,
    return_context=True
    )

print(response.answer)
print("CYPHER :", response.retriever_result.metadata["cypher"])
print("CONTEXT:", response.retriever_result.items)

driver.close()
