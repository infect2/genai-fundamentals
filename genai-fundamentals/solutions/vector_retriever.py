import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from dotenv import load_dotenv
load_dotenv()

from neo4j import GraphDatabase
# tag::import-embedder[]
from tools.llm_provider import create_neo4j_embeddings
# end::import-embedder[]
# tag::import-retriever[]
from neo4j_graphrag.retrievers import VectorRetriever
# end::import-retriever[]

# Connect to Neo4j database
driver = GraphDatabase.driver(
    os.getenv("NEO4J_URI"), 
    auth=(
        os.getenv("NEO4J_USERNAME"), 
        os.getenv("NEO4J_PASSWORD")
    )
)

# tag::embedder[]
# Create embedder
embedder = create_neo4j_embeddings()
# end::embedder[]

# tag::retriever[]
# Create retriever
retriever = VectorRetriever(
    driver,
    index_name="moviePlots",
    embedder=embedder,
    return_properties=["title", "plot"],
)
# end::retriever[]

# tag::search[]
# Search for similar items
result = retriever.search(query_text="Toys coming alive", top_k=5)
# end::search[]

# tag::print-results[]
# Parse results
for item in result.items:
    print(item.content, item.metadata["score"])
# end::print-results[]

# Close the database connection
driver.close()
