# GraphRAGService 제거 및 Agent-Only API 전환

## 개요

`api/service.py`(GraphRAGService)를 제거하고 `/agent/query` API만 제공.
AgentService가 Neo4j 연결, 세션 관리, RAG 파이프라인을 직접 처리.

---

## 현재 의존성 분석

### GraphRAGService를 사용하는 파일

| 파일 | 사용 방식 |
|------|----------|
| `api/server.py` | `/query`, `/reset`, `/sessions`, `/history` 엔드포인트 |
| `api/mcp_server.py` | `query`, `reset_session`, `list_sessions` 도구 |
| `api/a2a_server.py` | `graphrag_query` 스킬 |
| `api/agent/service.py` | `AgentService(graphrag_service)` 의존성 |
| `api/agent/tools.py` | `service.execute_*` 메서드 호출 (미존재!) |

### 핵심 발견

`agent/tools.py`가 호출하는 메서드들이 GraphRAGService에 존재하지 않음:
- `service.execute_cypher_rag()` ❌
- `service.execute_vector_rag()` ❌
- `service.execute_hybrid_rag()` ❌

이 메서드들은 `pipelines` 모듈의 독립 함수로만 존재.

---

## 수정/삭제 파일

| 파일 | 변경 |
|------|------|
| `api/service.py` | **삭제** |
| `api/router.py` | **삭제** (Agent가 직접 도구 선택) |
| `api/pipelines/` | **유지** (Agent 도구에서 사용) |
| `api/agent/service.py` | Neo4j 연결, 세션 관리 통합 |
| `api/agent/tools.py` | pipelines 직접 호출로 수정 |
| `api/server.py` | `/query` 등 제거, `/agent/query`만 유지 |
| `api/mcp_server.py` | `query` 도구 제거, `agent_query`만 유지 |
| `api/a2a_server.py` | `graphrag_query` 스킬 제거, `graphrag_agent`만 유지 |
| `api/__init__.py` | GraphRAGService export 제거 |
| `CLAUDE.md` | 문서 업데이트 |

---

## 구현 상세

### 1. `api/agent/service.py` 확장

```python
class AgentService:
    def __init__(self, model_name=None, neo4j_uri=None, ...):
        # Neo4j 연결 (기존 GraphRAGService에서 이동)
        self._graph = Neo4jGraph(...)

        # LLM 설정
        self._llm = create_langchain_llm(...)

        # Embeddings & Vector Store
        self._embeddings = create_langchain_embeddings()
        self._vector_store = None  # lazy init

        # Cypher Chain (pipelines에서 사용)
        self._cypher_chain = GraphCypherQAChain.from_llm(...)

        # LangGraph Agent
        self._agent_graph = create_agent_graph(self, model_name)

    # 세션 관리 (GraphRAGService에서 이동)
    def get_or_create_history(self, session_id): ...
    def reset_session(self, session_id): ...
    def list_sessions(self): ...
    def get_history_messages(self, session_id): ...

    # 스키마 조회
    def get_schema(self): ...

    # 파이프라인 실행 (Agent 도구용)
    def execute_cypher_rag(self, query): ...
    def execute_vector_rag(self, query, top_k): ...
    def execute_hybrid_rag(self, query, top_k): ...
```

### 2. `api/agent/tools.py` 수정

```python
def create_agent_tools(agent_service: "AgentService"):
    @tool
    def cypher_query(query: str) -> str:
        result = agent_service.execute_cypher_rag(query)
        ...
```

### 3. `api/server.py` 간소화

제거:
- `QueryRequest`, `QueryResponse` 모델
- `POST /query` 엔드포인트
- `POST /reset/{session_id}` → AgentService로 이동
- `GET /sessions` → AgentService로 이동
- `GET /history/{session_id}` → AgentService로 이동

유지:
- `GET /` (서버 상태)
- `POST /agent/query` (Agent 쿼리)
- `POST /agent/reset/{session_id}` (세션 리셋)
- `GET /agent/sessions` (세션 목록)
- `GET /agent/history/{session_id}` (대화 이력)

### 4. MCP Server 간소화

제거할 도구:
- `query` → `agent_query`로 대체
- `reset_session` → `agent_reset_session`으로 변경
- `list_sessions` → `agent_list_sessions`으로 변경

### 5. A2A Server 간소화

제거할 스킬:
- `graphrag_query` → `graphrag_agent`로 통합

---

## 구현 순서

1. `api/agent/service.py` 확장 (Neo4j 연결, 세션 관리, 파이프라인 실행 메서드 추가)
2. `api/agent/tools.py` 수정 (AgentService 메서드 호출)
3. `api/agent/graph.py` 수정 (AgentService 타입 힌트)
4. `api/server.py` 수정 (/query 제거, 세션 API를 /agent/ 하위로 이동)
5. `api/mcp_server.py` 수정 (query 도구 제거)
6. `api/a2a_server.py` 수정 (graphrag_query 스킬 제거)
7. `api/__init__.py` 수정 (GraphRAGService export 제거)
8. `api/service.py` 삭제
9. `api/router.py` 삭제
10. `CLAUDE.md` 문서 업데이트
11. 테스트 파일 업데이트

---

## 검증 방법

```bash
# 1. 서버 시작
python -m genai-fundamentals.api.server

# 2. Agent 쿼리 테스트
curl -X POST http://localhost:8000/agent/query \
  -H "Content-Type: application/json" \
  -d '{"query": "Which actors appeared in The Matrix?"}'

# 3. 세션 관리 테스트
curl http://localhost:8000/agent/sessions
curl -X POST http://localhost:8000/agent/reset/default

# 4. MCP 서버 테스트
pytest genai-fundamentals/tests/test_mcp_server.py -v

# 5. A2A 서버 테스트
pytest genai-fundamentals/tests/test_a2a_server.py -v
```

---

## Breaking Changes

- `/query` 엔드포인트 제거 → `/agent/query` 사용
- `/reset/{id}` → `/agent/reset/{id}`
- `/sessions` → `/agent/sessions`
- `/history/{id}` → `/agent/history/{id}`
- MCP `query` 도구 제거 → `agent_query` 사용
- A2A `graphrag_query` 스킬 제거 → `graphrag_agent` 사용
