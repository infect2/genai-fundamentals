# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Plan 저장 규칙

Plan 모드에서 계획을 작성할 때, `docs/` 디렉토리에도 복사본을 저장한다.
파일명 형식: `docs/<plan-name>.md`

## Security Programming Guidelines

코드를 작성하거나 수정할 때 반드시 보안 관점을 유지해야 한다.

### OWASP Top 10 준수

모든 코드 변경은 OWASP Top 10 가이드라인을 준수해야 한다:
- Injection (SQL, Command, LDAP 등)
- Broken Authentication
- Sensitive Data Exposure
- XML External Entities (XXE)
- Broken Access Control
- Security Misconfiguration
- Cross-Site Scripting (XSS)
- Insecure Deserialization
- Using Components with Known Vulnerabilities
- Insufficient Logging & Monitoring

### Input Validation

모든 사용자 입력은 처리 전에 검증하고 sanitize해야 한다:
- 화이트리스트 기반 검증 선호
- 특수 문자 이스케이프 처리
- SQL 쿼리는 항상 parameterized query 사용

### Secrets Management

API 키나 credential을 절대 하드코딩하지 않는다:
- 환경 변수 사용 (`.env` 파일)
- 민감한 정보가 포함된 파일은 `.gitignore`에 추가
- 커밋 전 credential 노출 여부 확인

### Memory Safety (C/C++ 해당 시)

- Buffer overflow 항상 체크
- 안전한 문자열 함수 사용 (`strncpy`, `snprintf` 등)
- 동적 메모리 할당 후 해제 확인

### Security Audit

코드 작성 후 mental security audit 수행:
1. 잠재적 취약점 식별
2. 입력 검증 누락 여부 확인
3. 민감 정보 노출 가능성 점검
4. 발견된 취약점 보고 및 수정

## Project Overview

**Capora AI Ontology Bot** - Neo4j 지식 그래프 기반 자연어 질의 시스템

이 저장소는 Neo4j 그래프 데이터베이스와 LLM을 활용한 지식 그래프 검색 애플리케이션입니다.
ReAct Agent를 통해 multi-step reasoning으로 복잡한 쿼리를 처리합니다.

## Commands

### Environment Setup
```bash
# Install dependencies
pip install -r requirements.txt

# Verify environment is configured correctly
python -m genai-fundamentals.tools.verify_environment
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
curl -X POST "http://localhost:8000/agent/query" \
  -H "Content-Type: application/json" \
  -d '{"query": "What entities are connected to X?"}'
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
| Context reset | ✅ Toggle | ❌ (Agent handles context) |
| API status | ✅ Sidebar | ✅ Start message |
| Detail info | ✅ Expander (Cypher) | ✅ Agent details (thoughts, tool_calls, iterations) |
| Commands | ❌ | ✅ `/settings`, `/reset`, `/help` |
| Action buttons | ❌ | ✅ Inline buttons |
| Google OAuth | ❌ | ✅ `@cl.oauth_callback` |
| API endpoint | `/query` | `/agent/query` |

**Note:** Chainlit은 Agent-Only API (`/agent/query`)를 사용합니다. Streamlit은 아직 레거시 `/query` 엔드포인트를 사용하며, Agent API로 마이그레이션이 필요합니다.

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

### A2A Server

```bash
# A2A 서버 시작 (기본 포트: 9000)
python -m genai-fundamentals.api.a2a_server

# 포트 지정
python -m genai-fundamentals.api.a2a_server --port 9000

# AgentCard 확인
curl http://localhost:9000/.well-known/agent.json
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
├── api/                        # REST API, MCP, A2A 서버
│   ├── __init__.py
│   ├── server.py               # FastAPI endpoints (v1 + v2)
│   ├── graphrag_service.py     # GraphRAG 오케스트레이션 (세션, 쿼리 라우팅)
│   ├── models.py               # 데이터 클래스 (TokenUsage, QueryResult)
│   ├── prompts.py              # 프롬프트 템플릿 모음
│   ├── router.py               # Query Router (쿼리 분류 및 라우팅)
│   ├── config.py               # 중앙 설정 (AppConfig, MultiAgentConfig)
│   ├── mcp_server.py           # MCP (Model Context Protocol) server
│   ├── a2a_server.py           # A2A (Agent2Agent) Protocol server
│   ├── pipelines/              # 라우트별 RAG 파이프라인
│   │   ├── __init__.py         # re-exports
│   │   ├── utils.py            # 공통 유틸리티
│   │   ├── cypher.py           # Cypher RAG (Text-to-Cypher)
│   │   ├── vector.py           # Vector RAG (시맨틱 검색)
│   │   ├── hybrid.py           # Hybrid RAG (Vector + Cypher)
│   │   ├── llm_only.py         # LLM Only (직접 응답)
│   │   └── memory.py           # Memory (사용자 정보 저장/조회)
│   ├── agent/                  # ReAct Agent (LangGraph 기반) - 단일 에이전트
│   │   ├── __init__.py
│   │   ├── graph.py            # LangGraph StateGraph 정의
│   │   ├── state.py            # AgentState TypedDict
│   │   ├── tools.py            # Agent 도구 정의
│   │   ├── prompts.py          # ReAct 시스템 프롬프트
│   │   └── service.py          # AgentService 클래스
│   ├── multi_agents/           # 멀티 에이전트 시스템 (v2)
│   │   ├── __init__.py         # 모듈 exports
│   │   ├── base.py             # BaseDomainAgent 추상 클래스
│   │   ├── registry.py         # AgentRegistry (에이전트 등록/조회)
│   │   ├── graph_factory.py    # 도메인 에이전트 그래프 팩토리
│   │   ├── orchestrator/       # Master Orchestrator
│   │   │   ├── router.py       # DomainRouter (도메인 라우팅)
│   │   │   ├── state.py        # OrchestratorState
│   │   │   ├── service.py      # OrchestratorService
│   │   │   └── prompts.py      # 의도 분석 프롬프트
│   │   ├── tms/                # TMS 도메인 에이전트
│   │   │   ├── agent.py        # TMSAgent 클래스
│   │   │   ├── tools.py        # TMS 전용 도구
│   │   │   └── prompts.py      # TMS 시스템 프롬프트
│   │   ├── wms/                # WMS 도메인 에이전트
│   │   ├── fms/                # FMS 도메인 에이전트
│   │   └── tap/                # TAP! 도메인 에이전트
│   ├── ontology/               # 통합 온톨로지
│   │   ├── __init__.py
│   │   ├── upper.py            # 상위 온톨로지 (Asset, Participant, Location)
│   │   ├── tms_schema.py       # TMS TBox
│   │   ├── wms_schema.py       # WMS TBox
│   │   ├── fms_schema.py       # FMS TBox
│   │   └── tap_schema.py       # TAP! TBox
│   └── logging/                # Elasticsearch 로깅
│       ├── __init__.py         # 모듈 exports
│       ├── config.py           # ES 클라이언트 설정
│       ├── schemas.py          # 로그 스키마 정의
│       └── middleware.py       # FastAPI 미들웨어
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
│   ├── verify_environment.py   # Environment configuration test
│   ├── verify_local_neo4j.py   # Local Neo4j connection test
│   ├── load_movie_data.py      # Sample movie data loader
│   ├── mine_evaluator.py       # MINE ontology validator
│   ├── generate_middlemile_owl.py  # Middlemile 물류 OWL 온톨로지 생성기
│   └── owl_to_neo4j.py         # OWL → Neo4j 변환 로더
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

**LangChain GraphRAG Pipeline (api/graphrag_service.py):**
1. Connect to Neo4j with `Neo4jGraph()`
2. Create LLM (`ChatOpenAI`)
3. **Query Router로 쿼리 분류 (cypher/vector/hybrid/llm_only/memory)**
4. 분류된 타입에 따라 적합한 RAG 파이프라인 선택
5. Execute queries with routing-based pipeline selection

### Retriever Types
- **VectorRetriever** - Basic vector similarity search on movie plots
- **VectorCypherRetriever** - Vector search enhanced with custom Cypher queries for graph traversal
- **Text2CypherRetriever** - Converts natural language to Cypher queries

## REST API Server (Agent-Only)

모든 쿼리는 ReAct Agent를 통해 처리됩니다.

### Files
- `api/server.py` - FastAPI endpoints (thin layer)
- `api/graphrag_service.py` - GraphRAG 오케스트레이션 (세션 관리, Agent가 내부적으로 사용)
- `api/models.py` - 데이터 클래스 (TokenUsage, QueryResult, StreamingCallbackHandler)
- `api/prompts.py` - 프롬프트 템플릿 모음
- `api/router.py` - Query Router (Agent 도구에서 내부적으로 사용)
- `api/pipelines/` - RAG 파이프라인 (Agent 도구에서 내부적으로 사용)

### Endpoints
| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Server status |
| GET | `/docs` | Swagger UI documentation |
| POST | `/agent/query` | Execute query with ReAct Agent (multi-step reasoning) |
| POST | `/reset/{session_id}` | Reset session context |
| GET | `/sessions` | List active sessions |
| GET | `/history/{session_id}` | Get conversation history |
| GET | `/cache/stats` | Query cache statistics |
| POST | `/cache/clear` | Clear query cache |

## MCP Server (Agent-Only)

MCP (Model Context Protocol) 서버는 MCP 프로토콜을 통해 지식 그래프 검색 기능을 제공합니다.
모든 쿼리는 ReAct Agent를 통해 처리됩니다.

### Files
- `api/mcp_server.py` - MCP server implementation
- `api/graphrag_service.py` - GraphRAG business logic (Agent가 내부적으로 사용)

### MCP Tools

| Tool | Description | Parameters |
|------|-------------|------------|
| `agent_query` | ReAct Agent로 자연어 쿼리 처리 (multi-step reasoning) | `query` (필수), `session_id` |
| `reset_session` | 세션 컨텍스트 초기화 | `session_id` (필수) |
| `list_sessions` | 활성 세션 목록 조회 | - |

### Agent Query Response Format
```json
{
  "answer": "The entities connected to X are...",
  "thoughts": ["Searching for connected entities...", ...],
  "tool_calls": [{"name": "cypher_query", "args": {...}}],
  "tool_results": [...],
  "iterations": 2,
  "token_usage": {
    "total_tokens": 1500,
    "prompt_tokens": 1200,
    "completion_tokens": 300,
    "total_cost": 0.0075
  }
}
```

### Usage Example (Python)
```python
# MCP 클라이언트에서 tool 호출
result = await client.call_tool("agent_query", {
    "query": "What entities are connected to X?",
    "session_id": "user123"
})
```

### Architecture Comparison

| Feature | REST API | MCP Server | A2A Server |
|---------|----------|------------|------------|
| Protocol | HTTP | stdio (JSON-RPC) | JSON-RPC 2.0 (HTTP) |
| Entry point | `api/server.py` | `api/mcp_server.py` | `api/a2a_server.py` |
| Business logic | `api/graphrag_service.py` | `api/graphrag_service.py` (shared) | `api/graphrag_service.py` (shared) |
| Streaming | SSE | Not supported | Not supported |
| Use case | Web apps, curl | Claude Desktop, AI assistants | Agent-to-Agent 통신 |
| Default port | 8000 | - | 9000 |

## A2A Server (Agent-Only)

A2A (Agent2Agent) 프로토콜 서버는 Google의 A2A Protocol을 통해 지식 그래프 검색 기능을 에이전트 간 통신으로 제공합니다.
모든 쿼리는 ReAct Agent를 통해 처리됩니다.

**A2A vs MCP:**
- MCP: Agent → Tools (에이전트가 도구를 호출)
- A2A: Agent → Agent (에이전트 간 대등한 통신)

### 실행 방법

```bash
# A2A 서버 시작 (기본 포트: 9000)
python -m genai-fundamentals.api.a2a_server

# 포트 지정
python -m genai-fundamentals.api.a2a_server --port 9000

# AgentCard 확인
curl http://localhost:9000/.well-known/agent.json | python -m json.tool
```

### AgentCard

AgentCard는 에이전트의 기능을 자기 기술하는 매니페스트입니다:

| Field | Value |
|-------|-------|
| Name | Capora AI Ontology Bot |
| URL | http://localhost:9000 |
| Input modes | text/plain, application/json |
| Output modes | text/plain, application/json |
| Streaming | No |

### Skills

| Skill ID | 설명 | 예시 쿼리 |
|----------|------|----------|
| `ontology_agent` | ReAct Agent multi-step reasoning | "What entities are connected to X?", "Y와 관련된 데이터를 찾아줘" |

### 쿼리 테스트

```bash
# 쿼리 (message/send)
curl -X POST http://localhost:9000/ \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": "1",
    "method": "message/send",
    "params": {
      "message": {
        "messageId": "msg-001",
        "role": "user",
        "parts": [{"kind": "text", "text": "What entities are connected to X?"}]
      }
    }
  }'
```

### 응답 형식

응답은 TextPart (자연어 답변) + DataPart (구조화 데이터)로 구성됩니다:

**Agent 응답 DataPart:**
```json
{
  "thoughts": ["First, I'll search for connected entities...", ...],
  "tool_calls": [{"name": "cypher_query", "args": {...}}],
  "iterations": 2,
  "token_usage": {"total_tokens": 1500, "total_cost": 0.0075}
}
```

### 주요 파일

| 파일 | 역할 |
|------|------|
| `api/a2a_server.py` | A2A 프로토콜 서버 (AgentCard, AgentExecutor) |
| `api/graphrag_service.py` | GraphRAG 비즈니스 로직 (공유) |
| `api/agent/service.py` | ReAct Agent 로직 (공유) |

## Query Router (Internal)

Query Router는 Agent 도구 내부에서 쿼리 유형에 따라 적합한 RAG 파이프라인을 자동 선택합니다.
API 엔드포인트로 직접 노출되지 않으며, Agent가 내부적으로 사용합니다.

### 라우트 타입

| Route | 설명 | 예시 쿼리 |
|-------|------|----------|
| `cypher` | 엔티티/관계 조회 (Text-to-Cypher) | "X와 연결된 엔티티는?" |
| `vector` | 시맨틱 검색 (Vector similarity) | "비슷한 특성을 가진 데이터 찾아줘" |
| `hybrid` | 복합 쿼리 (Vector + Cypher) | "특정 조건을 만족하는 유사 엔티티" |
| `llm_only` | 일반 질문 (DB 조회 없음) | "이것은 무엇인가요?" |
| `memory` | 사용자 정보 저장/조회 (Neo4j) | "내 차번호는 59구8426이야 기억해", "내 차번호 뭐지?" |

### 테스트

```bash
# Router 테스트 실행
pytest genai-fundamentals/tests/test_router.py -v

# Mock 테스트만 (API 호출 없음)
pytest genai-fundamentals/tests/test_router.py -v -k "mock"

# 통합 테스트 (OpenAI API 필요)
pytest genai-fundamentals/tests/test_router.py -v -k "integration"
```

## ReAct Agent

ReAct (Reasoning + Acting) Agent는 LangGraph를 사용하여 multi-step reasoning을 수행합니다.
모든 API 요청은 이 Agent를 통해 처리되며, Agent는 내부적으로 여러 도구를 조합하여 쿼리를 처리합니다.

### 아키텍처

```
사용자 쿼리
    ↓
┌─────────────────────────────────────────────────────┐
│                  ReAct Agent                        │
│  ┌─────────┐    ┌─────────┐    ┌─────────┐          │
│  │  Think  │ →  │   Act   │ →  │ Observe │ → (반복)  │
│  └─────────┘    └─────────┘    └─────────┘          │
│       ↓                                             │
│  [도구 선택]                                          │
│  - cypher_query: 엔티티/관계 조회                       │
│  - vector_search: 시맨틱 검색                          │
│  - hybrid_search: 복합 검색                           │
│  - get_schema: DB 스키마 조회                          │
└─────────────────────────────────────────────────────┘
    ↓
최종 답변
```

### 사용 예시

```bash
# REST API - ReAct Agent 사용
curl -X POST "http://localhost:8000/agent/query" \
  -H "Content-Type: application/json" \
  -d '{"query": "X와 유사한 특성을 가진 엔티티 찾아줘", "stream": false}'
```

### Agent Request Format
```json
{
  "query": "X와 유사한 특성을 가진 엔티티 찾아줘",
  "session_id": "user123",      // Optional (default: "default")
  "stream": false               // Optional (default: false)
}
```

### Agent Response Format (Non-streaming)
```json
{
  "answer": "Based on my search...",
  "thoughts": ["First, I'll find entities related to X...", "Now searching for similar entities..."],
  "tool_calls": [
    {"name": "cypher_query", "args": {"query": "entities connected to X"}},
    {"name": "vector_search", "args": {"query": "similar entities"}}
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

## Multi-Agent System (v2)

WMS, TMS, FMS, TAP! 서비스를 위한 연합형 멀티 에이전트 시스템입니다.
도메인별 전문 에이전트와 Master Orchestrator가 협력하여 복잡한 쿼리를 처리합니다.

### 아키텍처

```
사용자 쿼리
    ↓
┌─────────────────────────────────────────────────────┐
│              Master Orchestrator                     │
│  ┌──────────────────────────────────────────────┐   │
│  │           Domain Router                       │   │
│  │   쿼리 분석 → 도메인 선택 (WMS/TMS/FMS/TAP)    │   │
│  └──────────────────────────────────────────────┘   │
│       ↓ (single domain)    ↓ (cross-domain)         │
│  ┌─────────┐         ┌─────────┐  ┌─────────┐       │
│  │  Agent  │         │ Agent A │→ │ Agent B │       │
│  │ (단일)  │         │ (병렬/순차 실행)         │       │
│  └─────────┘         └─────────┘  └─────────┘       │
│       ↓                     ↓                        │
│  ┌──────────────────────────────────────────────┐   │
│  │           Response Synthesizer                │   │
│  │         (결과 통합 & 최종 응답 생성)           │   │
│  └──────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────┘
    ↓
최종 답변
```

### 도메인 에이전트

| 도메인 | 설명 | 주요 도구 |
|--------|------|----------|
| **WMS** | 창고 관리 시스템 | inventory_query, location_search, utilization |
| **TMS** | 운송 관리 시스템 | shipment_status, carrier_search, dispatch_query |
| **FMS** | 차량 관리 시스템 | vehicle_status, maintenance_schedule, driver_info |
| **TAP!** | 사용자 호출 서비스 | call_status, eta_query, booking_status |

### v2 API 엔드포인트

| Method | Path | Description |
|--------|------|-------------|
| POST | `/v2/query` | 멀티 에이전트 쿼리 실행 (자동 도메인 라우팅) |
| GET | `/v2/agents` | 등록된 도메인 에이전트 목록 |
| GET | `/v2/agents/{domain}/schema` | 도메인별 온톨로지 스키마 |

### v2 Request Format

```json
{
  "query": "배송 현황 알려줘",
  "session_id": "user123",
  "preferred_domain": "auto",      // auto | wms | tms | fms | tap
  "allow_cross_domain": true       // 크로스 도메인 허용 여부
}
```

### v2 Response Format

```json
{
  "answer": "현재 운송 중인 배송이 5건 있습니다...",
  "domain_decision": {
    "primary": "tms",
    "secondary": [],
    "confidence": 0.95,
    "reasoning": "배송 현황 조회 요청으로 TMS 도메인이 적합합니다.",
    "cross_domain": false
  },
  "agent_results": {
    "tms": {
      "answer": "...",
      "thoughts": [...],
      "tool_calls": [...],
      "iterations": 2
    }
  },
  "token_usage": {
    "total_tokens": 1500,
    "total_cost": 0.0075
  }
}
```

### 크로스 도메인 예시

```bash
# 정비 중인 차량을 배차에서 제외
curl -X POST http://localhost:8000/v2/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "정비 중인 차량을 오늘 배차에서 제외해줘",
    "allow_cross_domain": true
  }'

# 응답:
# - FMS Agent: 정비 중인 차량 목록 조회 (차량A, 차량B, 차량C)
# - TMS Agent: 해당 차량 배차에서 제외 처리
# - 통합 응답: "FMS에서 정비 중인 차량 3대를 TMS 배차에서 제외했습니다."
```

### 도메인 라우팅 키워드

| 도메인 | 키워드 |
|--------|--------|
| WMS | 창고, 재고, 적재, 입고, 출고, 보관, 피킹 |
| TMS | 배송, 배차, 운송, 운송사, 화주, 경로, 픽업 |
| FMS | 차량, 정비, 소모품, 운전자, 연비, 타이어 |
| TAP! | 호출, 예약, ETA, 결제, 피드백, 내 택배 |

### 테스트

```bash
# 도메인 라우터 테스트
pytest genai-fundamentals/tests/test_domain_router.py -v

# 도메인 에이전트 테스트
pytest genai-fundamentals/tests/test_domain_agents.py -v
```

### 주요 파일

| 파일 | 설명 |
|------|------|
| `api/multi_agents/base.py` | BaseDomainAgent 추상 클래스 |
| `api/multi_agents/registry.py` | AgentRegistry (에이전트 등록/조회) |
| `api/multi_agents/orchestrator/router.py` | DomainRouter (도메인 라우팅) |
| `api/multi_agents/orchestrator/service.py` | OrchestratorService (오케스트레이션) |
| `api/multi_agents/tms/agent.py` | TMSAgent 클래스 |
| `api/ontology/upper.py` | 상위 온톨로지 (공유 개념) |
| `api/ontology/tms_schema.py` | TMS 도메인 스키마 |

### 설정

```python
# api/config.py
@dataclass
class MultiAgentConfig:
    orchestrator_enabled: bool = True
    cross_domain_enabled: bool = True
    max_cross_domain_agents: int = 3
    routing_confidence_threshold: float = 0.7
```

환경변수:
```bash
MULTI_AGENT_ORCHESTRATOR_ENABLED=true
MULTI_AGENT_CROSS_DOMAIN_ENABLED=true
MULTI_AGENT_MAX_CROSS_DOMAIN=3
MULTI_AGENT_ROUTING_THRESHOLD=0.7
```

### Multi-Turn Conversation (대화 컨텍스트 유지)

Agent는 동일 세션 내에서 이전 대화 기록을 참조하여 연속적인 질의를 처리합니다.

**지원되는 표현:**
- "이전에", "앞서", "아까" (previous, earlier)
- "그 다음", "다음 것" (next ones)
- "나머지", "제외하고" (remaining, excluding)
- "방금 말한", "위에서 언급한" (just mentioned, mentioned above)

**사용 예시:**
```bash
# Turn 1: 첫 번째 쿼리
curl -X POST "http://localhost:8000/agent/query" \
  -H "Content-Type: application/json" \
  -d '{"query": "5명 shipper를 조회해", "session_id": "user123"}'
# 응답: 이유진 무역 80, 배민 상사, 정미영 무역 61, 정준호 무역 75, 강준호 무역 83

# Turn 2: 이전 결과 참조 쿼리
curl -X POST "http://localhost:8000/agent/query" \
  -H "Content-Type: application/json" \
  -d '{"query": "이전에 응답한 5명을 제외하고 다음 5명을 조회해", "session_id": "user123"}'
# 응답: 포스코 상사, 박지훈 무역 49, 박서연 무역 74, 정지훈 무역 87, 최지훈 무역 94 (다른 5명!)

# Turn 3: 컨텍스트 확인
curl -X POST "http://localhost:8000/agent/query" \
  -H "Content-Type: application/json" \
  -d '{"query": "지금까지 몇 명의 shipper를 조회했어?", "session_id": "user123"}'
# 응답: 총 10명
```

**설정:**
```python
agent_service = AgentService(
    graphrag_service,
    history_window=10    # 최근 10개 턴의 대화 기록 유지 (기본값)
)
```

**아키텍처:**
```
Turn 1 쿼리
    ↓
Agent 실행 → 응답 → 히스토리 저장 (HistoryCache + Neo4j)
    ↓
Turn 2 쿼리
    ↓
히스토리 로드 (최근 N턴) → Agent 컨텍스트에 주입 → Agent 실행
    ↓
이전 대화 참조하여 응답 생성
```

**주요 파일:**
| 파일 | 역할 |
|------|------|
| `api/agent/service.py` | `_load_history_messages()`, `history_window` 설정 |
| `api/agent/prompts.py` | Multi-Turn Context 처리 지침 |
| `api/graphrag_service.py` | `get_history_messages()`, `_add_to_history()` |
| `api/cache.py` | `HistoryCache` (메모리 캐시로 Neo4j 부하 감소) |

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
| `POST /agent/query` | Agent reasoning + Tool 내 LLM 호출 |
| MCP `agent_query` | Agent reasoning + Tool 내 LLM 호출 |
| A2A `graphrag_agent` | Agent reasoning + Tool 내 LLM 호출 |

### 관련 파일

| 파일 | 역할 |
|------|------|
| `api/models.py` | `TokenUsage` 데이터클래스 정의 |
| `api/graphrag_service.py` | `query()`에 callback 래핑 |
| `api/agent/service.py` | `query()`/`query_async()`/`query_stream()`에 callback 래핑 |
| `api/server.py` | `TokenUsageResponse` 응답 모델 |
| `api/mcp_server.py` | 응답 JSON에 token_usage 포함 |
| `api/a2a_server.py` | 응답 DataPart에 token_usage 포함 |

## Query Cache & Concurrency

Agent 쿼리 결과를 캐싱하고 동시 요청을 효율적으로 처리합니다.

### 주요 기능

| 기능 | 설명 |
|------|------|
| **LRU Cache** | TTL 기반 쿼리 결과 캐싱 |
| **Query Normalization** | 유사 쿼리 자동 매칭 |
| **Request Coalescing** | 동일 쿼리 동시 요청 병합 |
| **LLM Semaphore** | 동시 API 호출 수 제한 |

### 아키텍처

```
동시 요청 (Query A, Query A, Query B)
    ↓
┌─────────────────────────────────────────────────────┐
│           1. Query Cache (LRU + TTL)                 │
│     ├─ HIT  → 캐시된 결과 즉시 반환 (~0.01s)          │
│     └─ MISS ↓                                        │
├─────────────────────────────────────────────────────┤
│           2. Request Coalescer                       │
│     동일 쿼리 (Query A × 2) → 1회만 실행, 결과 공유    │
├─────────────────────────────────────────────────────┤
│           3. LLM Semaphore (max_concurrent=10)       │
│     동시 LLM API 호출 수 제한 → Rate Limit 방지       │
├─────────────────────────────────────────────────────┤
│           4. Agent 실행 → 결과 캐싱                   │
└─────────────────────────────────────────────────────┘
    ↓
응답
```

### 성능 지표

| 지표 | 값 | 설명 |
|------|-----|------|
| 캐시 히트 응답 시간 | ~0.01s | 317배 속도 향상 (vs. cold: 3.6s) |
| 동시 처리량 (warm cache) | 241.7 QPS | 목표 100 QPS 초과 달성 |
| 캐시 히트율 | 94.64% | 유사 쿼리 정규화로 높은 히트율 |
| 콜드 쿼리 응답 시간 | ~4.7s | LLM API 레이턴시 (고유 한계) |

### 쿼리 정규화 (Query Normalization)

유사한 쿼리가 동일한 캐시 키를 갖도록 다음 규칙으로 정규화합니다:

| 정규화 규칙 | 예시 | 결과 |
|------------|------|------|
| 소문자 변환 | "배송 현황 알려줘" | "배송 현황 알려줘" |
| 연속 공백 제거 | "배송  현황" | "배송 현황" |
| 숫자 플레이스홀더 | "상위 10개" | "상위 <N>개" |
| 한국어 조사 제거 | "배송을 알려줘" | "배송 알려줘" |
| 동사 통일 | "찾아줘", "조회해줘" | "보여줘" |
| 의문사 제거 | "뭐야?", "무엇인가요?" | "" |
| 기본 동사 추가 | "서울 물류센터" | "서울 물류센터 보여줘" |

**조사 제거 패턴:** 은/는, 이/가, 을/를, 의, 에, 에서, 으로, 로

### 설정

AgentService 생성 시 캐시 및 동시성 설정을 지정할 수 있습니다:

```python
agent_service = AgentService(
    graphrag_service,
    enable_cache=True,       # 캐싱 활성화 (기본: True)
    cache_ttl=300,           # TTL 5분 (기본값)
    max_concurrent_llm=10    # 최대 동시 LLM 호출 (기본: 10)
)
```

개별 컴포넌트 설정:

```python
from genai_fundamentals.api.cache import get_cache, get_coalescer, get_llm_semaphore

# 캐시 설정
cache = get_cache(
    max_size=1000,          # 최대 캐시 엔트리 수 (기본: 1000)
    default_ttl=300,        # 기본 TTL 5분 (기본: 300초)
    schema_ttl=3600         # 스키마 TTL 1시간 (기본: 3600초)
)

# Request Coalescer (자동 활성화)
coalescer = get_coalescer()

# LLM Semaphore
semaphore = get_llm_semaphore(max_concurrent=10)  # 최대 동시 호출 수
```

### API 엔드포인트

| Method | Path | Description |
|--------|------|-------------|
| GET | `/cache/stats` | 캐시 및 동시성 통계 조회 |
| POST | `/cache/clear` | 캐시 전체 삭제 |

**통계 응답 (확장됨):**
```json
{
  "cache": {
    "size": 56,
    "max_size": 1000,
    "hits": 892,
    "misses": 48,
    "evictions": 0,
    "coalesced": 23,
    "hit_rate": "94.89%",
    "schema_cached": true
  },
  "coalescer": {
    "in_flight": 2,
    "coalesced": 156,
    "executed": 234
  },
  "semaphore": {
    "max_concurrent": 10,
    "current": 3,
    "total_acquired": 500,
    "total_waited": 120,
    "utilization": "30.0%"
  }
}
```

| 필드 | 설명 |
|------|------|
| `cache.coalesced` | 병합된 요청 수 |
| `coalescer.in_flight` | 현재 실행 중인 고유 쿼리 수 |
| `coalescer.coalesced` | 병합되어 실행되지 않은 요청 수 |
| `semaphore.current` | 현재 동시 LLM 호출 수 |
| `semaphore.utilization` | Semaphore 사용률 |

### 캐시 바이패스

특정 쿼리에서 캐시를 사용하지 않으려면 `use_cache=False`를 지정합니다:

```python
# 동기 방식
result = agent_service.query(query_text, session_id, use_cache=False)

# 비동기 방식
result = await agent_service.query_async(query_text, session_id, use_cache=False)
```

**Note:** 스트리밍 응답(`query_stream`)은 캐싱되지 않습니다.

### 주요 파일

| 파일 | 역할 |
|------|------|
| `api/cache.py` | QueryCache, RequestCoalescer, LLMSemaphore |
| `api/agent/service.py` | AgentService 캐시/동시성 통합 |
| `api/server.py` | `/cache/stats`, `/cache/clear` 엔드포인트 |

### 모니터링

```bash
# 캐시 상태 확인
curl http://localhost:8000/cache/stats | python -m json.tool

# 캐시 초기화
curl -X POST http://localhost:8000/cache/clear
```

### 캐시 히트 확인

응답에 `cached: true`가 포함되면 캐시 히트입니다:

```json
{
  "answer": "...",
  "cached": true
}
```

## Elasticsearch Logging

REST API의 모든 request/response를 Elasticsearch로 전송하여 실시간 추적 및 검색할 수 있습니다.

### 아키텍처

```
Request → FastAPI Middleware → Agent Service → Response
              ↓                    ↓              ↓
         [request 로깅]      [domain 로깅]   [response 로깅]
              ↓                    ↓              ↓
              └──────────→ Elasticsearch ←────────┘
```

### 환경변수 설정

```bash
# .env 파일에서 설정
ES_LOGGING_ENABLED=true       # 로깅 활성화
ES_HOST=localhost             # Elasticsearch 호스트
ES_PORT=9200                  # Elasticsearch 포트
ES_INDEX_PREFIX=graphrag-logs # 인덱스 접두사
ES_API_KEY=                   # API 키 (인증 필요 시)
```

### 인덱스 패턴

- 인덱스명: `graphrag-logs-YYYY.MM.DD`
- 일별 자동 롤오버로 관리 용이

### 로그 이벤트 유형

| event_type | 설명 |
|------------|------|
| `request` | HTTP 요청 시작 시 |
| `response` | HTTP 응답 완료 시 |
| `agent_response` | Agent 쿼리 상세 응답 (thoughts, tool_calls 포함) |
| `error` | 에러 발생 시 |

### 로그 스키마

```json
{
  "timestamp": "2024-01-25T12:00:00.000Z",
  "request_id": "abc12345",
  "event_type": "agent_response",
  "http": {
    "method": "POST",
    "path": "/agent/query",
    "status_code": 200,
    "duration_ms": 1500.5
  },
  "request": {
    "query": "What entities are connected to X?",
    "session_id": "user123",
    "stream": false
  },
  "response": {
    "answer": "The entities connected to X are..."
  },
  "agent": {
    "thoughts": ["Searching for actors..."],
    "tool_calls": [{"name": "cypher_query", "args": {...}}],
    "iterations": 2
  },
  "token_usage": {
    "total_tokens": 1500,
    "prompt_tokens": 1200,
    "completion_tokens": 300,
    "total_cost": 0.0075
  },
  "client": {
    "ip": "127.0.0.1",
    "user_agent": "curl/7.79.1"
  }
}
```

### Elasticsearch 실행 (Docker)

```bash
# Elasticsearch 실행
docker run -d -p 9200:9200 -e "discovery.type=single-node" \
  -e "xpack.security.enabled=false" \
  elasticsearch:8.11.0

# 연결 확인
curl http://localhost:9200
```

### 로그 검색 예시 (Kibana/ES Query)

```json
// 특정 세션의 모든 쿼리
GET graphrag-logs-*/_search
{
  "query": {
    "term": { "request.session_id": "user123" }
  }
}

// 에러 조회
GET graphrag-logs-*/_search
{
  "query": {
    "term": { "event_type": "error" }
  }
}

// 느린 쿼리 (5초 이상)
GET graphrag-logs-*/_search
{
  "query": {
    "range": { "http.duration_ms": { "gte": 5000 } }
  }
}
```

### 주요 파일

| 파일 | 역할 |
|------|------|
| `api/logging/__init__.py` | 모듈 exports |
| `api/logging/config.py` | Elasticsearch 클라이언트 설정 |
| `api/logging/schemas.py` | 로그 스키마 정의 (Pydantic) |
| `api/logging/middleware.py` | FastAPI 미들웨어 |

### 검증 방법

```bash
# 1. Elasticsearch 실행
docker run -d -p 9200:9200 -e "discovery.type=single-node" \
  -e "xpack.security.enabled=false" elasticsearch:8.11.0

# 2. 환경변수 설정
export ES_LOGGING_ENABLED=true
export ES_HOST=localhost
export ES_PORT=9200

# 3. 서버 시작
python -m genai-fundamentals.api.server

# 4. 테스트 쿼리
curl -X POST http://localhost:8000/agent/query \
  -H "Content-Type: application/json" \
  -d '{"query": "What entities are connected to X?"}'

# 5. ES에서 로그 확인
curl http://localhost:9200/graphrag-logs-*/_search | python -m json.tool
```

## Configuration

Environment variables required in `.env` file (see `.env.example`):
- `LLM_PROVIDER` - LLM 프로바이더 선택 (`openai`/`bedrock`/`azure`/`google`, 기본값: `openai`)
- `NEO4J_URI` - Neo4j connection URI
- `NEO4J_USERNAME` - Neo4j username
- `NEO4J_PASSWORD` - Neo4j password

프로바이더별 추가 환경변수는 아래 "LLM Provider 설정" 섹션 참고.

## LLM Provider 설정

`tools/llm_provider.py` 팩토리 모듈을 통해 여러 LLM 프로바이더를 환경변수로 전환 가능합니다.

### 프로바이더 전환

```bash
# .env 파일에서 설정
LLM_PROVIDER="openai"   # openai (기본) | bedrock | azure | google
```

### 프로바이더별 환경변수

| Provider | 필수 환경변수 |
|----------|--------------|
| `openai` | `OPENAI_API_KEY`, `OPENAI_MODEL`, `OPENAI_EMBEDDING_MODEL` |
| `bedrock` | `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION`, `BEDROCK_MODEL_ID`, `BEDROCK_EMBEDDING_MODEL_ID` |
| `azure` | `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_DEPLOYMENT`, `AZURE_OPENAI_EMBEDDING_DEPLOYMENT`, `AZURE_OPENAI_API_VERSION` |
| `google` | `GOOGLE_PROJECT_ID`, `GOOGLE_LOCATION`, `VERTEX_MODEL`, `VERTEX_EMBEDDING_MODEL` |

### 팩토리 함수

| 함수 | 레이어 | 설명 |
|------|--------|------|
| `create_langchain_llm()` | LangChain | API 서버용 ChatModel 생성 |
| `create_langchain_embeddings()` | LangChain | API 서버용 Embeddings 생성 |
| `create_neo4j_llm()` | neo4j-graphrag | exercises/solutions용 LLM 생성 |
| `create_neo4j_embeddings()` | neo4j-graphrag | exercises/solutions용 Embedder 생성 |
| `get_token_tracker()` | 공통 | 프로바이더별 토큰 추적 컨텍스트 매니저 |
| `get_router_model_name()` | 공통 | 라우터용 경량 모델명 반환 |

### 벡터 인덱스 호환성

Neo4j `moviePlots` 인덱스는 OpenAI `text-embedding-ada-002` (1536차원)으로 생성됨.
호환되지 않는 프로바이더 사용 시 경고가 출력됩니다.

| Provider | Embedding Model | Dimension | 호환성 |
|----------|----------------|-----------|--------|
| openai | text-embedding-ada-002 | 1536 | O |
| azure | text-embedding-ada-002 | 1536 | O |
| bedrock | amazon.titan-embed-text-v2:0 | 1024 | X (재인덱싱 필요) |
| google | text-embedding-004 | 768 | X (재인덱싱 필요) |

### 토큰 추적

| Provider | 방법 | 비용 계산 |
|----------|------|----------|
| openai/azure | `get_openai_callback()` | O (정확) |
| bedrock/google | `GenericTokenTracker` | 토큰 수만 (비용 0.0) |

### 사용 예시

```python
# LangChain (API 서버)
from genai_fundamentals.tools.llm_provider import (
    create_langchain_llm, create_langchain_embeddings, get_token_tracker
)

llm = create_langchain_llm(temperature=0)
embeddings = create_langchain_embeddings()

with get_token_tracker() as tracker:
    result = chain.invoke(...)
print(tracker.total_tokens, tracker.total_cost)

# neo4j-graphrag (exercises/solutions)
from genai_fundamentals.tools.llm_provider import create_neo4j_llm, create_neo4j_embeddings

llm = create_neo4j_llm(model_params={"temperature": 0})
embedder = create_neo4j_embeddings()
```

## Dependencies

Key packages in `requirements.txt`:
- `neo4j-graphrag[openai]` - Neo4j GraphRAG library
- `langchain`, `langchain-openai`, `langchain-neo4j` - LangChain framework
- `langchain-aws` - AWS Bedrock LangChain integration
- `langchain-google-vertexai` - Google Vertex AI LangChain integration
- `boto3` - AWS SDK (Bedrock용)
- `langgraph` - LangGraph for ReAct Agent
- `fastapi`, `uvicorn` - REST API server
- `mcp` - Model Context Protocol server
- `a2a-sdk[http-server]` - A2A (Agent2Agent) Protocol server
- `streamlit`, `chainlit` - Chat client UI frameworks
- `python-dotenv` - Environment variable management
- `elasticsearch` - Elasticsearch logging (optional)
- `rdflib` - OWL/RDF ontology generation and parsing

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
python -m genai-fundamentals.tools.verify_local_neo4j
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

## Middlemile Logistics OWL 생성기

Middlemile 물류 시스템을 위한 OWL 온톨로지 데이터를 생성하는 도구입니다.
Neo4j에 로드하기 위한 테스트 데이터를 OWL/Turtle 형식으로 생성합니다.

### 실행 방법

```bash
# 기본 실행 (화주 100, 운송사 100, 배송 500건)
python -m genai-fundamentals.tools.generate_middlemile_owl

# 커스텀 수량 지정
python -m genai-fundamentals.tools.generate_middlemile_owl [화주수] [운송사수] [배송수]
python -m genai-fundamentals.tools.generate_middlemile_owl 50 50 200
```

### 출력 파일

| 파일 | 형식 | 설명 |
|------|------|------|
| `data/middlemile_ontology.owl` | RDF/XML | OWL 온톨로지 파일 |
| `data/middlemile_ontology.ttl` | Turtle | 사람이 읽기 쉬운 형식 |

### 온톨로지 스키마

**Classes (클래스):**
| 클래스 | 한국어 | 설명 |
|--------|--------|------|
| `Shipper` | 화주 | 화물을 보내는 기업/개인 |
| `Carrier` | 운송사 | 운송 서비스를 제공하는 기업 |
| `Vehicle` | 차량 | 운송사가 보유한 차량 |
| `Cargo` | 화물 | 운송 대상 물품 |
| `Location` | 위치 | 물류 관련 장소 (상위 클래스) |
| `LogisticsCenter` | 물류센터 | 화물 집하/분류 시설 |
| `Port` | 항구 | 해상 운송 항만 |
| `Shipment` | 배송 | 화물 운송 건 |
| `MatchingService` | 매칭서비스 | 화주-운송사 매칭 |
| `PricingService` | 가격책정서비스 | 동적 가격 책정 |
| `ConsolidationService` | 합적서비스 | 화물 합적 |

**Object Properties (관계):**
| 속성 | 설명 | Domain → Range |
|------|------|----------------|
| `owns` | 소유 | Shipper → Cargo |
| `operates` | 운영 | Carrier → Vehicle |
| `assignedTo` | 배정 | Shipment → Vehicle |
| `contains` | 포함 | Shipment → Cargo |
| `origin` | 출발지 | Shipment → Location |
| `destination` | 목적지 | Shipment → Location |
| `requestedBy` | 요청자 | Shipment → Shipper |
| `fulfilledBy` | 수행자 | Shipment → Carrier |
| `matchesShipper` | 화주매칭 | MatchingService → Shipper |
| `matchesCarrier` | 운송사매칭 | MatchingService → Carrier |
| `consolidates` | 합적화물 | ConsolidationService → Cargo |
| `prices` | 가격책정대상 | PricingService → Shipment |
| `locatedAt` | 위치함 | Carrier → Location |
| `servesRegion` | 서비스지역 | Carrier → Location |

### 생성되는 데이터

| 항목 | 기본 수량 | 설명 |
|------|----------|------|
| 화주 (Shipper) | 100개 | 한국 기업명 기반 |
| 운송사 (Carrier) | 100개 | 물류 회사명 기반 |
| 차량 (Vehicle) | 1~100대/운송사 | 10종 차량 유형 |
| 물류센터 | 15개 | 대한민국 주요 물류센터 |
| 항구 | 10개 | 대한민국 주요 항구 |
| 배송 (Shipment) | 500건 | 6가지 상태 |
| 매칭서비스 | 200건 | 화주-운송사 매칭 |
| 가격책정 | 300건 | 동적 가격 |
| 합적서비스 | 50건 | 2~5개 화물 합적 |

### 차량 유형

| 유형 | 적재용량(kg) | 적재용량(m³) |
|------|-------------|-------------|
| 1톤 트럭 | 1,000 | 3.5 |
| 2.5톤 트럭 | 2,500 | 8.5 |
| 5톤 트럭 | 5,000 | 17.0 |
| 11톤 트럭 | 11,000 | 36.0 |
| 25톤 트럭 | 25,000 | 65.0 |
| 윙바디 | 15,000 | 50.0 |
| 냉동/냉장차 | 8,000 | 28.0 |
| 컨테이너 | 20,000 | 60.0 |
| 탱크로리 | 18,000 | 30.0 |
| 평판차 | 12,000 | 40.0 |

### 배송 상태

| 상태 | 설명 |
|------|------|
| `requested` | 요청됨 |
| `matched` | 매칭됨 |
| `pickup_pending` | 픽업 대기 |
| `in_transit` | 운송 중 |
| `delivered` | 배송 완료 |
| `cancelled` | 취소됨 |

### 네임스페이스

| Prefix | URI |
|--------|-----|
| `mm:` | `http://capora.ai/ontology/middlemile#` |
| `mmi:` | `http://capora.ai/ontology/middlemile/instance#` |

### 사용 예시 (Python)

```python
from rdflib import Graph

# OWL 파일 로드
g = Graph()
g.parse("data/middlemile_ontology.ttl", format="turtle")

# 모든 화주 조회
for shipper in g.subjects(RDF.type, MM.Shipper):
    name = g.value(shipper, MM.name)
    print(f"화주: {name}")

# 특정 운송사의 차량 조회
for vehicle in g.objects(carrier_uri, MM.operates):
    plate = g.value(vehicle, MM.licensePlate)
    print(f"차량: {plate}")
```

## OWL to Neo4j 변환기

OWL/RDF 온톨로지 파일을 Neo4j 그래프 데이터베이스로 변환하여 로드하는 도구입니다.

### 실행 방법

```bash
# 기본 실행 (data/middlemile_ontology.ttl 파일 로드)
python -m genai-fundamentals.tools.owl_to_neo4j

# 특정 파일 지정
python -m genai-fundamentals.tools.owl_to_neo4j data/middlemile_ontology.owl

# 기존 데이터 삭제 후 로드
python -m genai-fundamentals.tools.owl_to_neo4j data/middlemile_ontology.ttl --clear

# Neo4j 연결 정보 지정
python -m genai-fundamentals.tools.owl_to_neo4j --uri neo4j://localhost:7687 --username neo4j --password mypassword
```

### 지원 포맷

| 확장자 | 포맷 |
|--------|------|
| `.ttl` | Turtle |
| `.owl` | RDF/XML |
| `.rdf` | RDF/XML |
| `.xml` | RDF/XML |
| `.nt` | N-Triples |
| `.n3` | Notation3 |

### 변환 규칙

| OWL/RDF | Neo4j | 예시 |
|---------|-------|------|
| Class Instance | Node (라벨=클래스명) | `mm:Shipper` → `(:Shipper)` |
| Object Property | Relationship | `mm:operates` → `[:OPERATES]` |
| Data Property | Node Property | `mm:name` → `{name: "..."}` |
| URI local name | `uri` 속성 | `mmi:Shipper_001` → `{uri: "Shipper_001"}` |
| rdfs:label@ko | `name` 속성 (한국어 우선) | `"한진 상사"@ko` → `{name: "한진 상사"}` |

### 관계 타입 변환

| OWL Property | Neo4j Relationship |
|--------------|-------------------|
| `mm:owns` | `[:OWNS]` |
| `mm:operates` | `[:OPERATES]` |
| `mm:assignedTo` | `[:ASSIGNED_TO]` |
| `mm:requestedBy` | `[:REQUESTED_BY]` |
| `mm:fulfilledBy` | `[:FULFILLED_BY]` |
| `mm:matchesShipper` | `[:MATCHES_SHIPPER]` |
| `mm:matchesCarrier` | `[:MATCHES_CARRIER]` |

### 환경변수

| 변수 | 기본값 | 설명 |
|------|--------|------|
| `NEO4J_URI` | `neo4j://127.0.0.1:7687` | Neo4j 연결 URI |
| `NEO4J_USERNAME` | `neo4j` | Neo4j 사용자명 |
| `NEO4J_PASSWORD` | - | Neo4j 비밀번호 |

### 전체 워크플로우

```bash
# 1. OWL 데이터 생성
python -m genai-fundamentals.tools.generate_middlemile_owl

# 2. Neo4j에 로드 (기존 데이터 삭제)
python -m genai-fundamentals.tools.owl_to_neo4j --clear

# 3. Neo4j Browser에서 확인
# http://localhost:7474
# MATCH (n) RETURN n LIMIT 100
```

### 샘플 Cypher 쿼리

```cypher
-- 모든 화주 조회
MATCH (s:Shipper) RETURN s LIMIT 10

-- 운송사와 보유 차량
MATCH (c:Carrier)-[:OPERATES]->(v:Vehicle)
RETURN c.name, count(v) as vehicles
ORDER BY vehicles DESC

-- 특정 배송의 전체 경로
MATCH (shipper:Shipper)<-[:REQUESTED_BY]-(s:Shipment)-[:FULFILLED_BY]->(carrier:Carrier)
MATCH (s)-[:ORIGIN]->(origin:Location)
MATCH (s)-[:DESTINATION]->(dest:Location)
MATCH (s)-[:ASSIGNED_TO]->(vehicle:Vehicle)
MATCH (s)-[:CONTAINS]->(cargo:Cargo)
RETURN shipper.name, carrier.name, origin.name, dest.name,
       vehicle.licensePlate, cargo.cargoType, s.status

-- 지역별 물류센터
MATCH (lc:LogisticsCenter)
RETURN lc.name, lc.address, lc.latitude, lc.longitude

-- 화주-운송사 매칭 현황
MATCH (m:MatchingService)-[:MATCHES_SHIPPER]->(s:Shipper)
MATCH (m)-[:MATCHES_CARRIER]->(c:Carrier)
RETURN s.name as shipper, c.name as carrier, m.matchScore
ORDER BY m.matchScore DESC

-- 합적 서비스 현황
MATCH (cs:ConsolidationService)-[:CONSOLIDATES]->(cargo:Cargo)
RETURN cs.uri, collect(cargo.cargoType) as cargos, count(cargo) as count
```

### 출력 예시

```
============================================================
OWL to Neo4j 변환
============================================================

입력 파일: data/middlemile_ontology.ttl
Neo4j URI: neo4j://127.0.0.1:7687

1. OWL 파일 로드 중...
   - 4,836개 트리플 로드 완료

2. RDF 데이터 파싱 중...
   트리플 분석 중...
   - 노드: 700개
   - 관계: 1,245개

...

============================================================
변환 완료!
============================================================

통계:
  - 총 트리플 수: 4,836
  - 생성된 노드: 700
  - 생성된 관계: 1,245
  - 설정된 속성: 3,500
```
