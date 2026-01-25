# /query 엔드포인트 제거 (Agent-Only API)

## 개요

`POST /query` 엔드포인트만 제거하고 `/agent/query`만 제공.
GraphRAGService는 공통 모듈로 유지, AgentService가 이를 사용.

---

## 변경 범위

| 파일 | 변경 |
|------|------|
| `api/server.py` | `POST /query` 제거, 나머지 유지 |
| `api/mcp_server.py` | `query` 도구 제거 |
| `api/a2a_server.py` | `graphrag_query` 스킬 제거 |
| `CLAUDE.md` | 문서 업데이트 |

### 유지되는 것

- `api/service.py` (GraphRAGService) - 공통 모듈로 유지
- `api/router.py` - Agent 도구에서 내부적으로 사용 가능
- `api/pipelines/` - 유지
- `GET /`, `POST /reset/{id}`, `GET /sessions`, `GET /history/{id}` - 유지
- `POST /agent/query` - 유지

---

## 구현 상세

### 1. `api/server.py` 수정

제거:
- `QueryRequest` 모델
- `QueryResponse` 모델
- `POST /query` 엔드포인트 함수

유지:
- `GET /` (서버 상태)
- `POST /reset/{session_id}` (세션 리셋)
- `GET /sessions` (세션 목록)
- `GET /history/{session_id}` (대화 이력)
- `POST /agent/query` (Agent 쿼리)

### 2. `api/mcp_server.py` 수정

제거:
- `query` 도구 (tool)

유지:
- `agent_query` 도구
- `reset_session` 도구
- `list_sessions` 도구

### 3. `api/a2a_server.py` 수정

제거:
- `graphrag_query` 스킬

유지:
- `graphrag_agent` 스킬

---

## 구현 순서

1. `api/server.py` 수정 (POST /query 제거)
2. `api/mcp_server.py` 수정 (query 도구 제거)
3. `api/a2a_server.py` 수정 (graphrag_query 스킬 제거)
4. `CLAUDE.md` 문서 업데이트
5. 테스트 파일 업데이트

---

## 검증 방법

```bash
# 1. 서버 시작
python -m genai-fundamentals.api.server

# 2. /query 제거 확인 (404 반환)
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"query": "test"}'
# Expected: 404 Not Found

# 3. Agent 쿼리 테스트
curl -X POST http://localhost:8000/agent/query \
  -H "Content-Type: application/json" \
  -d '{"query": "Which actors appeared in The Matrix?"}'

# 4. 세션 관리 (기존대로 동작)
curl http://localhost:8000/sessions
curl -X POST http://localhost:8000/reset/default
```

---

## Breaking Changes

- `POST /query` 엔드포인트 제거 → `POST /agent/query` 사용
- MCP `query` 도구 제거 → `agent_query` 사용
- A2A `graphrag_query` 스킬 제거 → `graphrag_agent` 사용
