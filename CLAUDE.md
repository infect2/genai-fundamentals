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
python -m genai-fundamentals.tools.test_environment
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
python -m genai-fundamentals.exercises.text2cypher_rag
```

### Running API Server
```bash
# Start the REST API server
python -m genai-fundamentals.api.server

# Or with uvicorn (with auto-reload)
uvicorn genai-fundamentals.api.server:app --reload --port 8000

# Test the server
curl http://localhost:8000/
curl -X POST "http://localhost:8000/query" \
  -H "Content-Type: application/json" \
  -d '{"query": "Which actors appeared in The Matrix?"}'
```

### Streamlit Client
```bash
# Start the Streamlit chat client
streamlit run genai-fundamentals/clients/streamlit_app.py

# Access at http://localhost:8501
```

### Chainlit Client
```bash
# Start the Chainlit chat client (default port: 8000)
chainlit run genai-fundamentals/clients/chainlit_app.py

# Or specify a different port
chainlit run genai-fundamentals/clients/chainlit_app.py --port 8502

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
├── api/                        # REST API 서버
│   ├── __init__.py
│   ├── server.py               # FastAPI endpoints
│   └── service.py              # GraphRAG business logic (LangChain)
├── clients/                    # 채팅 클라이언트
│   ├── __init__.py
│   ├── chainlit_app.py         # Chainlit chat interface
│   └── streamlit_app.py        # Streamlit chat interface
├── exercises/                  # RAG 실습 파일
│   ├── __init__.py
│   ├── vector_retriever.py     # Basic vector similarity search
│   ├── vector_rag.py           # Vector RAG pipeline
│   ├── vector_cypher_rag.py    # Vector + Cypher RAG
│   └── text2cypher_rag.py      # Text-to-Cypher RAG
├── tools/                      # 유틸리티 도구
│   ├── __init__.py
│   ├── test_environment.py     # Environment configuration test
│   ├── test_local_neo4j.py     # Local Neo4j connection test
│   ├── load_movie_data.py      # Sample movie data loader
│   └── mine_evaluator.py       # MINE ontology validator
└── solutions/                  # Complete working implementations
```

### Exercise Pattern
Each exercise file in `genai-fundamentals/exercises/` has a corresponding solution in `genai-fundamentals/solutions/`. Students complete the exercises; solutions demonstrate the full implementation.

### Key Patterns Used

**Neo4j GraphRAG Pipeline (neo4j-graphrag library):**
1. Connect to Neo4j with `GraphDatabase.driver()`
2. Create an embedder (`OpenAIEmbeddings`)
3. Create a retriever (one of: `VectorRetriever`, `VectorCypherRetriever`, `Text2CypherRetriever`)
4. Create an LLM (`OpenAILLM`)
5. Build the pipeline with `GraphRAG(retriever=retriever, llm=llm)`
6. Execute queries with `rag.search(query_text=..., retriever_config={"top_k": N})`

**LangChain GraphRAG Pipeline (api/server.py):**
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
- `api/server.py` - FastAPI endpoints (thin layer)
- `api/service.py` - GraphRAG business logic

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

## MINE Evaluator (Ontology Validator)

MINE (Measure of Information in Nodes and Edges) Evaluator는 Knowledge Graph의 품질을 평가하는 도구입니다.

**참고 자료:**
- 논문: [arXiv:2502.09956 - KGGen](https://arxiv.org/abs/2502.09956)
- 블로그: [The Jaguar Problem](https://medium.com/@aiwithakashgoyal/the-jaguar-problem-the-ontology-nightmare-haunting-your-knowledge-graph-07aed203d256)

### 실행 방법
```bash
python -m genai-fundamentals.tools.mine_evaluator
```

### 평가 지표

| 지표 | 가중치 | 설명 |
|------|--------|------|
| Semantic Similarity | 50% | 원본 텍스트와 그래프 재구성 텍스트 간 유사도 (OpenAI Embeddings) |
| Ontology Coherence | 30% | 정의된 온톨로지 스키마 준수율 |
| Type Consistency | 20% | 엔티티 타입 일관성 (Jaguar Problem 탐지) |

### Jaguar Problem

동음이의어로 인한 엔티티 타입 혼동 문제:
- 예: "Jaguar"가 자동차인지 동물인지 잘못 분류
- MINE은 타입 제약 조건을 통해 이러한 문제를 탐지

### 온톨로지 스키마

`MOVIE_ONTOLOGY_SCHEMA`에 정의된 검증 규칙:

```python
{
    "node_types": {
        "Movie": {"required_properties": ["title"], ...},
        "Actor": {"required_properties": ["name"], ...},
        ...
    },
    "relationship_types": {
        "ACTED_IN": {"source": "Actor", "target": "Movie"},
        "DIRECTED": {"source": "Director", "target": "Movie"},
        ...
    },
    "type_constraints": {
        "Actor": {"cannot_be": ["Movie", "Genre"]},
        ...
    }
}
```

### 사용 예시

```python
from genai_fundamentals.tools.mine_evaluator import MINEEvaluator

evaluator = MINEEvaluator(
    neo4j_uri="neo4j://localhost:7687",
    neo4j_user="neo4j",
    neo4j_password="password"
)

result = evaluator.evaluate()
evaluator.print_report(result)

# 결과 접근
print(f"Overall: {result.overall_score}")
print(f"Semantic: {result.semantic_similarity}")
print(f"Ontology: {result.ontology_coherence}")
print(f"Type: {result.type_consistency}")
```

### 출력 예시

```
============================================================
MINE (Measure of Information in Nodes and Edges) Report
============================================================

Overall Score: 100.00%

Component Scores:
  - Semantic Similarity (50%): 100.00%
  - Ontology Coherence  (30%): 100.00%
  - Type Consistency    (20%): 100.00%

Graph Statistics:
  - Total Nodes: 59
  - Total Relationships: 78
============================================================
```

## Local Neo4j Support

### 연결 테스트
```bash
python -m genai-fundamentals.tools.test_local_neo4j
```

### 샘플 데이터 로드
```bash
python -m genai-fundamentals.tools.load_movie_data
```

### Neo4j Desktop 설정
1. APOC 플러그인 설치 필요 (Plugins → APOC → Install)
2. `.env` 파일에서 URI 설정:
   - 로컬 직접 실행: `NEO4J_URI="neo4j://127.0.0.1:7687"`
   - Docker에서 호스트 연결: `NEO4J_URI="neo4j://host.docker.internal:7687"`
