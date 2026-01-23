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
| Google OAuth | ❌ | ✅ `@cl.oauth_callback` |

### Chainlit Google OAuth 설정

Chainlit 클라이언트는 Google OAuth를 통한 인증을 지원합니다.

**사전 준비:**
1. [Google Cloud Console](https://console.cloud.google.com/) → APIs & Services → Credentials
2. OAuth 2.0 Client ID 생성 (Web application)
3. Authorized redirect URI: `http://localhost:8502/auth/oauth/google/callback`

**환경변수 설정 (`.env`):**
```bash
OAUTH_GOOGLE_CLIENT_ID="your-client-id"
OAUTH_GOOGLE_CLIENT_SECRET="your-client-secret"
CHAINLIT_AUTH_SECRET="your-secret"   # chainlit create-secret 으로 생성
```

**실행:**
```bash
chainlit run genai-fundamentals/clients/chainlit_app.py --port 8502
# → http://localhost:8502 접속 시 Google 로그인 화면 표시
```

### MCP Server

```bash
# stdio 모드 (Claude Desktop이 자동 실행)
python -m genai-fundamentals.api.mcp_server

# HTTP/SSE 모드 (URL 기반, 수동 실행 필요)
python -m genai-fundamentals.api.mcp_server_http --port 3001

# HTTPS 모드 (SSL 인증서 필요)
python -m genai-fundamentals.api.mcp_server_http --port 3001 --ssl
```

**Claude Desktop 설정** (`~/Library/Application Support/Claude/claude_desktop_config.json`):

stdio 모드 (권장):
```json
{
  "mcpServers": {
    "graphrag": {
      "command": "/path/to/.pyenv/shims/python3",
      "args": ["-m", "genai-fundamentals.api.mcp_server"],
      "cwd": "/path/to/genai-fundamentals",
      "env": {
        "PYTHONPATH": "/path/to/genai-fundamentals"
      }
    }
  }
}
```

HTTP/SSE 모드:
```json
{
  "mcpServers": {
    "graphrag": {
      "url": "https://localhost:3001/sse"
    }
  }
}
```

**MCP 테스트:**
```bash
pytest genai-fundamentals/tests/test_mcp_server.py -v -k "not neo4j"
```

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
├── api/                        # REST API 서버 및 MCP 서버
│   ├── __init__.py
│   ├── server.py               # FastAPI endpoints
│   ├── service.py              # GraphRAG business logic (LangChain)
│   ├── router.py               # Query Router (쿼리 분류 및 라우팅)
│   ├── mcp_server.py           # MCP (Model Context Protocol) server
│   └── agent/                  # ReAct Agent (LangGraph 기반)
│       ├── __init__.py
│       ├── graph.py            # LangGraph StateGraph 정의
│       ├── state.py            # AgentState TypedDict
│       ├── tools.py            # Agent 도구 정의
│       ├── prompts.py          # ReAct 시스템 프롬프트
│       └── service.py          # AgentService 클래스
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

**LangChain GraphRAG Pipeline (api/service.py):**
1. Connect to Neo4j with `Neo4jGraph()`
2. Create LLM (`ChatOpenAI`)
3. **Query Router로 쿼리 분류 (cypher/vector/hybrid/llm_only/memory)**
4. 분류된 타입에 따라 적합한 RAG 파이프라인 선택
5. Execute queries with routing-based pipeline selection

### Retriever Types
- **VectorRetriever** - Basic vector similarity search on movie plots
- **VectorCypherRetriever** - Vector search enhanced with custom Cypher queries for graph traversal
- **Text2CypherRetriever** - Converts natural language to Cypher queries

## REST API Server

### Files
- `api/server.py` - FastAPI endpoints (thin layer)
- `api/service.py` - GraphRAG business logic
- `api/router.py` - Query Router (쿼리 분류)

### Endpoints
| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Server status |
| GET | `/docs` | Swagger UI documentation |
| POST | `/query` | Execute natural language query (with auto-routing) |
| POST | `/agent/query` | Execute query with ReAct Agent (multi-step reasoning) |
| POST | `/reset/{session_id}` | Reset session context |
| GET | `/sessions` | List active sessions |

### Query Request Format
```json
{
  "query": "Which actors appeared in The Matrix?",
  "session_id": "user123",      // Optional (default: "default")
  "reset_context": false,       // Optional (default: false)
  "stream": false,              // Optional (default: false)
  "force_route": null           // Optional: "cypher", "vector", "hybrid", "llm_only", "memory"
}
```

### Query Response Format (Non-streaming)
```json
{
  "answer": "Hugo Weaving, Laurence Fishburne...",
  "cypher": "MATCH (a:Actor)-[:ACTED_IN]->(m:Movie)...",
  "context": ["{'a.name': 'Hugo Weaving'}", ...],
  "route": "cypher",
  "route_reasoning": "특정 영화 제목으로 배우 조회",
  "token_usage": {
    "total_tokens": 641,
    "prompt_tokens": 590,
    "completion_tokens": 51,
    "total_cost": 0.001985
  }
}
```

### Streaming Response (SSE)
When `stream: true`, response is Server-Sent Events:
```
data: {"type": "metadata", "cypher": "...", "context": [...], "route": "cypher", "route_reasoning": "..."}
data: {"type": "token", "content": "Hugo "}
data: {"type": "token", "content": "Weaving"}
...
data: {"type": "done", "token_usage": {"total_tokens": 641, "prompt_tokens": 590, "completion_tokens": 51, "total_cost": 0.001985}}
```

## MCP Server

MCP (Model Context Protocol) 서버는 REST API와 동일한 비즈니스 로직(`service.py`)을 공유하면서 MCP 프로토콜을 통해 GraphRAG 기능을 제공합니다.

### Files
- `api/mcp_server.py` - MCP server implementation
- `api/service.py` - GraphRAG business logic (shared with REST API)

### MCP Tools

| Tool | Description | Parameters |
|------|-------------|------------|
| `query` | 자연어로 Neo4j 그래프 쿼리 | `query` (필수), `session_id`, `reset_context` |
| `agent_query` | ReAct Agent로 복잡한 쿼리 처리 (multi-step reasoning) | `query` (필수), `session_id` |
| `reset_session` | 세션 컨텍스트 초기화 | `session_id` (필수) |
| `list_sessions` | 활성 세션 목록 조회 | - |

### Query Tool Response Format
```json
{
  "answer": "Hugo Weaving, Laurence Fishburne...",
  "cypher": "MATCH (a:Actor)-[:ACTED_IN]->(m:Movie)...",
  "context": ["{'a.name': 'Hugo Weaving'}", ...],
  "token_usage": {
    "total_tokens": 641,
    "prompt_tokens": 590,
    "completion_tokens": 51,
    "total_cost": 0.001985
  }
}
```

### Usage Example (Python)
```python
# MCP 클라이언트에서 tool 호출
result = await client.call_tool("query", {
    "query": "Which actors appeared in The Matrix?",
    "session_id": "user123"
})
```

### Architecture Comparison

| Feature | REST API | MCP Server |
|---------|----------|------------|
| Protocol | HTTP | stdio (JSON-RPC) |
| Entry point | `api/server.py` | `api/mcp_server.py` |
| Business logic | `api/service.py` | `api/service.py` (shared) |
| Streaming | SSE | Not supported |
| Use case | Web apps, curl | Claude Desktop, AI agents |

## Query Router

Query Router는 쿼리 유형에 따라 적합한 RAG 파이프라인을 자동 선택합니다.

### 아키텍처

```
사용자 쿼리
    ↓
┌─────────────────┐
│  Query Router   │ ← LLM 기반 쿼리 분류
└────────┬────────┘
         ↓
    ┌────┴────┬─────────┬─────────┬─────────┐
    ↓         ↓         ↓         ↓         ↓
 cypher    vector    hybrid   llm_only   memory
  RAG       RAG       RAG     (직접응답)  (저장/조회)
```

### 라우트 타입

| Route | 설명 | 예시 쿼리 |
|-------|------|----------|
| `cypher` | 엔티티/관계 조회 (Text-to-Cypher) | "톰 행크스가 출연한 영화는?" |
| `vector` | 시맨틱 검색 (Vector similarity) | "슬픈 영화 추천해줘" |
| `hybrid` | 복합 쿼리 (Vector + Cypher) | "90년대 액션 영화 중 평점 높은 것" |
| `llm_only` | 일반 질문 (DB 조회 없음) | "영화란 무엇인가요?" |
| `memory` | 사용자 정보 저장/조회 (Neo4j) | "내 차번호는 59구8426이야 기억해", "내 차번호 뭐지?" |

### 사용 예시

```bash
# 자동 라우팅 (기본)
curl -X POST "http://localhost:8000/query" \
  -H "Content-Type: application/json" \
  -d '{"query": "톰 행크스가 출연한 영화는?"}'
# → route: "cypher"

# 강제 라우팅 (특정 파이프라인 지정)
curl -X POST "http://localhost:8000/query" \
  -H "Content-Type: application/json" \
  -d '{"query": "슬픈 영화", "force_route": "vector"}'
# → route: "vector" (강제)
```

### 테스트

```bash
# Router 테스트 실행
pytest genai-fundamentals/tests/test_router.py -v

# Mock 테스트만 (API 호출 없음)
pytest genai-fundamentals/tests/test_router.py -v -k "mock"

# 통합 테스트 (OpenAI API 필요)
pytest genai-fundamentals/tests/test_router.py -v -k "integration"
```

### 라우팅 비활성화

```python
# 라우팅 없이 항상 Cypher RAG 사용
service = GraphRAGService(enable_routing=False)
```

## ReAct Agent

ReAct (Reasoning + Acting) Agent는 LangGraph를 사용하여 multi-step reasoning을 수행합니다.
Query Router가 단일 분류로 파이프라인을 선택하는 반면, Agent는 여러 도구를 조합하여 복잡한 쿼리를 처리합니다.

### 아키텍처

```
사용자 쿼리
    ↓
┌─────────────────────────────────────────────────────┐
│                  ReAct Agent                         │
│  ┌─────────┐    ┌─────────┐    ┌─────────┐         │
│  │  Think  │ → │   Act   │ → │ Observe │ → (반복)  │
│  └─────────┘    └─────────┘    └─────────┘         │
│       ↓                                              │
│  [도구 선택]                                         │
│  - cypher_query: 엔티티/관계 조회                   │
│  - vector_search: 시맨틱 검색                       │
│  - hybrid_search: 복합 검색                         │
│  - get_schema: DB 스키마 조회                       │
└─────────────────────────────────────────────────────┘
    ↓
최종 답변
```

### Query Router vs ReAct Agent

| 특성 | Query Router (`/query`) | ReAct Agent (`/agent/query`) |
|------|------------------------|------------------------------|
| 추론 방식 | 단일 분류 | Multi-step reasoning |
| 도구 사용 | 1개 파이프라인 | 여러 도구 조합 가능 |
| 적합한 쿼리 | 단순 질문 | 복잡한 질문 |
| 응답 속도 | 빠름 | 상대적으로 느림 |
| 토큰 비용 | 낮음 | 높음 |

### 사용 예시

```bash
# REST API - ReAct Agent 사용
curl -X POST "http://localhost:8000/agent/query" \
  -H "Content-Type: application/json" \
  -d '{"query": "톰 행크스와 비슷한 배우가 출연한 SF 영화는?", "stream": false}'
```

### Agent Request Format
```json
{
  "query": "톰 행크스와 비슷한 배우가 출연한 SF 영화는?",
  "session_id": "user123",      // Optional (default: "default")
  "stream": false               // Optional (default: false)
}
```

### Agent Response Format (Non-streaming)
```json
{
  "answer": "Based on my search...",
  "thoughts": ["First, I'll find Tom Hanks movies...", "Now searching for similar actors..."],
  "tool_calls": [
    {"name": "cypher_query", "args": {"query": "Tom Hanks movies"}},
    {"name": "vector_search", "args": {"query": "sci-fi movies"}}
  ],
  "tool_results": [...],
  "iterations": 3,
  "token_usage": {
    "total_tokens": 2500,
    "prompt_tokens": 2100,
    "completion_tokens": 400,
    "total_cost": 0.0125
  }
}
```

### Streaming Response (SSE)
When `stream: true`, response is Server-Sent Events:
```
data: {"type": "token", "content": "Let me "}
data: {"type": "tool_call", "tool": "cypher_query", "input": {...}}
data: {"type": "tool_result", "result": "..."}
data: {"type": "token", "content": "Based on..."}
data: {"type": "done", "final_answer": "...", "token_usage": {"total_tokens": 2500, "prompt_tokens": 2100, "completion_tokens": 400, "total_cost": 0.0125}}
```

### 테스트

```bash
# Agent 테스트 실행
pytest genai-fundamentals/tests/test_agent.py -v

# Mock 테스트만 (API 호출 없음)
pytest genai-fundamentals/tests/test_agent.py -v -k "mock"

# 통합 테스트 (OpenAI API 및 Neo4j 필요)
pytest genai-fundamentals/tests/test_agent.py -v -k "integration"
```

### 주요 파일

| 파일 | 설명 |
|------|------|
| `api/agent/graph.py` | LangGraph StateGraph 정의 (Reason → Tool → Loop) |
| `api/agent/state.py` | AgentState TypedDict |
| `api/agent/tools.py` | cypher_query, vector_search, hybrid_search, get_schema |
| `api/agent/prompts.py` | ReAct 시스템 프롬프트 |
| `api/agent/service.py` | AgentService 클래스 (통합 인터페이스) |

### 무한 루프 방지

`MAX_ITERATIONS = 10`으로 설정되어 있어 최대 10번의 reasoning loop 후 강제 종료됩니다.

## Token Usage Tracking

모든 쿼리 파이프라인(Router, RAG, Agent)에서 발생하는 LLM 토큰 사용량을 추적합니다.

### 구현 방식

LangChain의 `get_openai_callback()` 컨텍스트 매니저를 사용하여 블록 내 모든 OpenAI API 호출의 토큰 사용량을 자동 집계합니다.

### 데이터 구조

```python
@dataclass
class TokenUsage:
    total_tokens: int = 0       # 총 토큰 수
    prompt_tokens: int = 0      # 프롬프트 토큰 수
    completion_tokens: int = 0  # 완성 토큰 수
    total_cost: float = 0.0     # 총 비용 (USD)
```

### 적용 범위

| 엔드포인트 | 추적 대상 |
|-----------|----------|
| `POST /query` | Router 분류 + RAG 파이프라인 (cypher/vector/hybrid/llm_only/memory) |
| `POST /agent/query` | Agent reasoning + Tool 내 LLM 호출 |
| MCP `query` | Router 분류 + RAG 파이프라인 (cypher/vector/hybrid/llm_only/memory) |
| MCP `agent_query` | Agent reasoning + Tool 내 LLM 호출 |

### 관련 파일

| 파일 | 역할 |
|------|------|
| `api/service.py` | `TokenUsage` 데이터클래스 정의, `query()`에 callback 래핑 |
| `api/agent/service.py` | `query()`/`query_async()`/`query_stream()`에 callback 래핑 |
| `api/server.py` | `TokenUsageResponse` 응답 모델 |
| `api/mcp_server.py` | 응답 JSON에 token_usage 포함 |

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
- `langgraph` - LangGraph for ReAct Agent
- `fastapi`, `uvicorn` - REST API server
- `mcp` - Model Context Protocol server
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
- `UserMemory` (session_id, key, value, updated_at)

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
