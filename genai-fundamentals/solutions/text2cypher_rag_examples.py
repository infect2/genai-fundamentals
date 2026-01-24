import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from dotenv import load_dotenv
load_dotenv()

from neo4j import GraphDatabase
from neo4j_graphrag.generation import GraphRAG
from neo4j_graphrag.retrievers import Text2CypherRetriever
from tools.llm_provider import create_neo4j_llm

# Connect to Neo4j database
driver = GraphDatabase.driver(
    os.getenv("NEO4J_URI"), 
    auth=(
        os.getenv("NEO4J_USERNAME"), 
        os.getenv("NEO4J_PASSWORD")
    )
)

# Create Cypher LLM
t2c_llm = create_neo4j_llm(model_params={"temperature": 0})

# tag::examples[]
# Cypher examples as input/query pairs
examples = [
    "USER INPUT: 'Get user ratings for a movie?' QUERY: MATCH (u:User)-[r:RATED]->(m:Movie) WHERE m.title = 'Movie Title' RETURN r.rating"
]
# end::examples[]

# tag::retriever[]
# Build the retriever
retriever = Text2CypherRetriever(
    driver=driver,
    llm=t2c_llm,
    examples=examples,
)
# end::retriever[]

llm = create_neo4j_llm()
rag = GraphRAG(retriever=retriever, llm=llm)

query_text = "What is the highest rating for Goodfellas?"
query_text = "What is the averaging user rating for the movie Toy Story?"
query_text = "What user gives the lowest ratings?"

response = rag.search(
    query_text=query_text,
    return_context=True
    )

print(response.answer)
print("CYPHER :", response.retriever_result.metadata["cypher"])
print("CONTEXT:", response.retriever_result.items)

driver.close()
