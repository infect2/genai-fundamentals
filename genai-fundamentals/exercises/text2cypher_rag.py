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

# Create LLM
t2c_llm = create_neo4j_llm(model_params={"temperature": 0})

# Define Neo4j schema
neo4j_schema = """
Nodes:
- Movie (title, plot, year, released, countries, languages)
- Actor (name, born)
- Director (name, born)
- Genre (name)
- User (name, userId)

Relationships:
- (Actor)-[:ACTED_IN]->(Movie)
- (Director)-[:DIRECTED]->(Movie)
- (Movie)-[:IN_GENRE]->(Genre)
- (User)-[:RATED {rating: float}]->(Movie)

Note: Movie titles with articles are stored as "Title, The" format (e.g., "Matrix, The", "Godfather, The")
"""

# Define few-shot examples
examples = [
    "Q: Which actors appeared in The Matrix?\nCypher: MATCH (a:Actor)-[:ACTED_IN]->(m:Movie) WHERE m.title = 'Matrix, The' RETURN a.name",
    "Q: What movies did Tom Hanks star in?\nCypher: MATCH (a:Actor {name: 'Tom Hanks'})-[:ACTED_IN]->(m:Movie) RETURN m.title",
    "Q: What genre is Toy Story?\nCypher: MATCH (m:Movie {title: 'Toy Story'})-[:IN_GENRE]->(g:Genre) RETURN g.name",
    "Q: Who directed The Godfather?\nCypher: MATCH (d:Director)-[:DIRECTED]->(m:Movie) WHERE m.title = 'Godfather, The' RETURN d.name"
]

# Build the retriever
retriever = Text2CypherRetriever(
    driver=driver,
    llm=t2c_llm,
    neo4j_schema=neo4j_schema,
    examples=examples,
) 

llm = create_neo4j_llm()
rag = GraphRAG(retriever=retriever, llm=llm)

query_text = input("Enter your query: ")

response = rag.search(
    query_text=query_text,
    return_context=True
    )

print(response.answer)
print("CYPHER :", response.retriever_result.metadata["cypher"])
print("CONTEXT:", response.retriever_result.items)

driver.close()
