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
pip install -r requirements.txt
python -m genai-fundamentals.tools.verify_environment
```

### Running Tests
```bash
pytest genai-fundamentals/solutions/test_solutions.py -v
pytest genai-fundamentals/solutions/test_solutions.py::test_vector_rag -v
```

### Running Individual Scripts
```bash
python -m genai-fundamentals.solutions.vector_rag
python -m genai-fundamentals.exercises.text2cypher_rag
```

### Running Servers
```bash
# REST API
python -m genai-fundamentals.api.server
uvicorn genai-fundamentals.api.server:app --reload --port 8000

# Streamlit Client
streamlit run genai-fundamentals/clients/streamlit_app.py

# Chainlit Client
chainlit run genai-fundamentals/clients/chainlit_app.py --port 8502

# MCP Server (stdio)
python -m genai-fundamentals.api.mcp_server

# MCP Server (HTTP/SSE)
python -m genai-fundamentals.api.mcp_server_http --port 3001

# A2A Server
python -m genai-fundamentals.api.a2a_server --port 9000

# Docker
docker-compose up -d
```

## Architecture

### Directory Structure
```
genai-fundamentals/
├── api/                        # REST API, MCP, A2A 서버
│   ├── server.py               # FastAPI endpoints (v1 + v2)
│   ├── graphrag_service.py     # GraphRAG 오케스트레이션 (세션, 쿼리 라우팅)
│   ├── models.py               # 데이터 클래스 (TokenUsage, QueryResult)
│   ├── prompts.py              # 프롬프트 템플릿 모음
│   ├── router.py               # Query Router (쿼리 분류 및 라우팅)
│   ├── config.py               # 중앙 설정 (AppConfig, MultiAgentConfig)
│   ├── mcp_server.py           # MCP server
│   ├── a2a_server.py           # A2A server
│   ├── cache.py                # QueryCache, RequestCoalescer, LLMSemaphore
│   ├── pipelines/              # 라우트별 RAG 파이프라인
│   │   ├── cypher.py           # Cypher RAG (Text-to-Cypher)
│   │   ├── vector.py           # Vector RAG (시맨틱 검색)
│   │   ├── hybrid.py           # Hybrid RAG (Vector + Cypher)
│   │   ├── llm_only.py         # LLM Only (직접 응답)
│   │   └── memory.py           # Memory (사용자 정보 저장/조회)
│   ├── agent/                  # ReAct Agent (LangGraph 기반)
│   │   ├── graph.py            # LangGraph StateGraph 정의
│   │   ├── state.py            # AgentState TypedDict
│   │   ├── tools.py            # Agent 도구 정의
│   │   ├── prompts.py          # ReAct 시스템 프롬프트
│   │   └── service.py          # AgentService 클래스
│   ├── multi_agents/           # 멀티 에이전트 시스템 (v2)
│   │   ├── base.py             # BaseDomainAgent 추상 클래스
│   │   ├── registry.py         # AgentRegistry
│   │   ├── graph_factory.py    # 도메인 에이전트 그래프 팩토리
│   │   ├── orchestrator/       # Master Orchestrator (router, state, service, prompts)
│   │   ├── tms/                # TMS 도메인 에이전트
│   │   ├── wms/                # WMS 도메인 에이전트
│   │   ├── fms/                # FMS 도메인 에이전트
│   │   ├── tap/                # TAP! 도메인 에이전트
│   │   └── memory/             # Memory 도메인 에이전트
│   ├── ontology/               # 통합 온톨로지 (upper, tms/wms/fms/tap_schema)
│   └── logging/                # Elasticsearch 로깅 (config, schemas, middleware)
├── clients/                    # 채팅 클라이언트 (chainlit_app, streamlit_app)
├── exercises/                  # RAG 실습 파일
├── tools/                      # 유틸리티 도구 (verify, load_data, OWL 생성기 등)
└── solutions/                  # Complete working implementations
```

### Exercise Pattern
Each exercise file in `genai-fundamentals/exercises/` has a corresponding solution in `genai-fundamentals/solutions/`.

### Key Patterns Used

**Neo4j GraphRAG Pipeline (neo4j-graphrag library):**
1. Connect to Neo4j with `GraphDatabase.driver()`
2. Create an embedder (`OpenAIEmbeddings`)
3. Create a retriever (`VectorRetriever`, `VectorCypherRetriever`, or `Text2CypherRetriever`)
4. Create an LLM (`OpenAILLM`)
5. Build the pipeline with `GraphRAG(retriever=retriever, llm=llm)`
6. Execute queries with `rag.search(query_text=..., retriever_config={"top_k": N})`

**LangChain GraphRAG Pipeline (api/graphrag_service.py):**
1. Connect to Neo4j with `Neo4jGraph()`
2. Create LLM (`ChatOpenAI`)
3. Query Router로 쿼리 분류 (cypher/vector/hybrid/llm_only/memory)
4. 분류된 타입에 따라 적합한 RAG 파이프라인 선택
5. Execute queries with routing-based pipeline selection

## Configuration

Environment variables required in `.env` file (see `.env.example`):
- `LLM_PROVIDER` - LLM 프로바이더 (`openai`/`bedrock`/`azure`/`google`, 기본값: `openai`)
- `NEO4J_URI` - Neo4j connection URI
- `NEO4J_USERNAME` - Neo4j username
- `NEO4J_PASSWORD` - Neo4j password
- `OPENAI_API_KEY` - OpenAI API key (when using openai provider)

## Dependencies

Key packages in `requirements.txt`:
- `neo4j-graphrag[openai]` - Neo4j GraphRAG library
- `langchain`, `langchain-openai`, `langchain-neo4j` - LangChain framework
- `langchain-aws` - AWS Bedrock integration
- `langchain-google-vertexai` - Google Vertex AI integration
- `langgraph` - LangGraph for ReAct Agent
- `fastapi`, `uvicorn` - REST API server
- `mcp` - Model Context Protocol server
- `a2a-sdk[http-server]` - A2A Protocol server
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
