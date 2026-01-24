import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from dotenv import load_dotenv
load_dotenv()

from neo4j import GraphDatabase
from neo4j_graphrag.retrievers import VectorRetriever
from neo4j_graphrag.generation import GraphRAG
from tools.llm_provider import create_neo4j_llm, create_neo4j_embeddings

# Connect to Neo4j database
driver = GraphDatabase.driver(
    os.getenv("NEO4J_URI"), 
    auth=(
        os.getenv("NEO4J_USERNAME"), 
        os.getenv("NEO4J_PASSWORD")
    )
)

# Create embedder
embedder = create_neo4j_embeddings()

# Create retriever
retriever = VectorRetriever(
    driver,
    index_name="moviePlots",
    embedder=embedder,
    return_properties=["title", "plot"],
)

# Create the LLM
llm = create_neo4j_llm(model_params={"temperature": 1})

# Create GraphRAG pipeline
rag = GraphRAG(retriever=retriever, llm=llm)

# Search
query_text = "Find me movies about toys coming alive"

response = rag.search(
    query_text=query_text,
    retriever_config={"top_k": 5},
    return_context=True
)

print(response.answer)
print("CONTEXT:", response.retriever_result.items)

# Close the database connection
driver.close()