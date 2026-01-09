# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This repository accompanies the [Neo4j and GenerativeAI Fundamentals course](https://graphacademy.neo4j.com/courses/genai-fundamentals) on GraphAcademy. It teaches how to build GraphRAG applications using Neo4j and OpenAI.

## Commands

### Environment Setup
```bash
# Install dependencies
pip install -r requirements.txt

# Verify environment is configured correctly
python genai-fundamentals/test_environment.py
```

### Running Tests
```bash
# Run all solution tests
pytest genai-fundamentals/solutions/test_solutions.py -v

# Run a specific test
pytest genai-fundamentals/solutions/test_solutions.py::test_vector_rag -v
```

### Running Individual Scripts
```bash
# Run from repository root (modules are imported by name)
python -m genai-fundamentals.solutions.vector_rag
python -m genai-fundamentals.text2cypher_rag
```

### Running API Server
```bash
# Start the REST API server
python -m genai-fundamentals.api_server

# Or with uvicorn (with auto-reload)
uvicorn genai-fundamentals.api_server:app --reload --port 8000

# Test the server
curl http://localhost:8000/
curl -X POST "http://localhost:8000/query" \
  -H "Content-Type: application/json" \
  -d '{"query": "Which actors appeared in The Matrix?"}'
```

### Streamlit Client
```bash
# Start the Streamlit chat client
streamlit run genai-fundamentals/streamlit_client.py

# Access at http://localhost:8501
```

### Chainlit Client
```bash
# Start the Chainlit chat client (default port: 8000)
chainlit run genai-fundamentals/chainlit_client.py

# Or specify a different port
chainlit run genai-fundamentals/chainlit_client.py --port 8502

# Access at http://localhost:8000 (or specified port)
```

### Client Comparison

| Feature | Streamlit | Chainlit |
|---------|-----------|----------|
| Chat interface | ✅ | ✅ |
| Streaming support | ✅ Toggle | ✅ Toggle |
| Context reset | ✅ Toggle | ✅ Toggle |
| API status | ✅ Sidebar | ✅ Start message |
| Detail info (Cypher) | ✅ Expander | ✅ Text Element |
| Commands | ❌ | ✅ `/settings`, `/reset`, `/help` |
| Action buttons | ❌ | ✅ Inline buttons |

### Docker

```bash
# Build and run with docker-compose (recommended)
docker-compose up -d

# View logs
docker logs graphrag-api

# Stop
docker-compose down

# Rebuild after code changes
docker-compose build --no-cache
docker-compose up -d
```

**Manual Docker commands:**
```bash
# Build image
docker build -t graphrag-api .

# Run container
docker run -p 8000:8000 --env-file .env graphrag-api

# Run with environment variables
docker run -p 8000:8000 \
  -e NEO4J_URI=neo4j+s://xxx.databases.neo4j.io \
  -e NEO4J_USERNAME=neo4j \
  -e NEO4J_PASSWORD=password \
  -e OPENAI_API_KEY=sk-xxx \
  graphrag-api
```

**Docker files:**
| File | Description |
|------|-------------|
| `Dockerfile` | Multi-stage build with security settings |
| `docker-compose.yml` | Container orchestration with health checks |
| `.dockerignore` | Build context optimization |

## Architecture

### Directory Structure
```
genai-fundamentals/
├── api_server.py           # FastAPI REST API server (endpoints only)
├── graph_rag_service.py    # GraphRAG business logic (LangChain-based)
├── streamlit_client.py     # Streamlit chat client (connects to API)
├── chainlit_client.py      # Chainlit chat client (connects to API)
├── vector_retriever.py     # Basic vector similarity search exercise
├── vector_rag.py           # Vector RAG pipeline exercise
├── vector_cypher_rag.py    # Vector + Cypher RAG exercise
├── text2cypher_rag.py      # Text-to-Cypher RAG exercise
└── solutions/              # Complete working implementations
```

### Exercise Pattern
Each exercise file in `genai-fundamentals/` has a corresponding solution in `genai-fundamentals/solutions/`. Students complete the exercises; solutions demonstrate the full implementation.

### Key Patterns Used

**Neo4j GraphRAG Pipeline (neo4j-graphrag library):**
1. Connect to Neo4j with `GraphDatabase.driver()`
2. Create an embedder (`OpenAIEmbeddings`)
3. Create a retriever (one of: `VectorRetriever`, `VectorCypherRetriever`, `Text2CypherRetriever`)
4. Create an LLM (`OpenAILLM`)
5. Build the pipeline with `GraphRAG(retriever=retriever, llm=llm)`
6. Execute queries with `rag.search(query_text=..., retriever_config={"top_k": N})`

**LangChain GraphRAG Pipeline (api_server.py):**
1. Connect to Neo4j with `Neo4jGraph()`
2. Create LLM (`ChatOpenAI`)
3. Define Cypher generation prompt with few-shot examples
4. Build chain with `GraphCypherQAChain.from_llm()`
5. Execute queries with `chain.invoke({"query": ...})`

### Retriever Types
- **VectorRetriever** - Basic vector similarity search on movie plots
- **VectorCypherRetriever** - Vector search enhanced with custom Cypher queries for graph traversal
- **Text2CypherRetriever** - Converts natural language to Cypher queries

## REST API Server

### Files
- `api_server.py` - FastAPI endpoints (thin layer)
- `graph_rag_service.py` - GraphRAG business logic

### Endpoints
| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Server status |
| GET | `/docs` | Swagger UI documentation |
| POST | `/query` | Execute natural language query |
| POST | `/reset/{session_id}` | Reset session context |
| GET | `/sessions` | List active sessions |

### Query Request Format
```json
{
  "query": "Which actors appeared in The Matrix?",
  "session_id": "user123",      // Optional (default: "default")
  "reset_context": false,       // Optional (default: false)
  "stream": false               // Optional (default: false)
}
```

### Query Response Format (Non-streaming)
```json
{
  "answer": "Hugo Weaving, Laurence Fishburne...",
  "cypher": "MATCH (a:Actor)-[:ACTED_IN]->(m:Movie)...",
  "context": ["{'a.name': 'Hugo Weaving'}", ...]
}
```

### Streaming Response (SSE)
When `stream: true`, response is Server-Sent Events:
```
data: {"type": "metadata", "cypher": "...", "context": [...]}
data: {"type": "token", "content": "Hugo "}
data: {"type": "token", "content": "Weaving"}
...
data: {"type": "done"}
```

## Configuration

Environment variables required in `.env` file (see `.env.example`):
- `OPENAI_API_KEY` - OpenAI API key
- `NEO4J_URI` - Neo4j connection URI
- `NEO4J_USERNAME` - Neo4j username
- `NEO4J_PASSWORD` - Neo4j password

## Dependencies

Key packages in `requirements.txt`:
- `neo4j-graphrag[openai]` - Neo4j GraphRAG library
- `langchain`, `langchain-openai`, `langchain-neo4j` - LangChain framework
- `fastapi`, `uvicorn` - REST API server
- `streamlit`, `chainlit` - Chat client UI frameworks
- `python-dotenv` - Environment variable management

## Test Framework

Tests use pytest with a custom `TestHelpers` fixture in `conftest.py` that:
- Loads `.env` automatically via `load_dotenv()`
- Provides `run_module()` to execute Python modules and capture stdout
- Supports mocking stdin for interactive scripts

## Data Model

The Neo4j database contains movie data with the following schema:

**Nodes:**
- `Movie` (title, plot, year, released, countries, languages)
- `Actor` (name, born)
- `Director` (name, born)
- `Genre` (name)
- `User` (name, userId)

**Relationships:**
- `(Actor)-[:ACTED_IN]->(Movie)`
- `(Director)-[:DIRECTED]->(Movie)`
- `(Movie)-[:IN_GENRE]->(Genre)`
- `(User)-[:RATED {rating: float}]->(Movie)`

**Note:** Movie titles with articles are stored as "Title, The" format (e.g., "Matrix, The", "Godfather, The")
