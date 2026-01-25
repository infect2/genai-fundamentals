"""
A2A Server Integration Tests (Agent-Only)

A2A (Agent2Agent) 서버의 기능을 테스트합니다.
- AgentCard 조회
- graphrag_agent 스킬 (ReAct Agent)
- 에러 처리

실행 방법:
    # 모든 A2A 테스트 실행 (서버 자동 시작)
    pytest genai-fundamentals/tests/test_a2a_server.py -v

    # Mock 테스트만 (API 호출 없음)
    pytest genai-fundamentals/tests/test_a2a_server.py -v -k "mock"

    # 통합 테스트 (Neo4j + OpenAI 필요, A2A 서버 자동 시작)
    pytest genai-fundamentals/tests/test_a2a_server.py -v -k "integration"
"""

import pytest
import subprocess
import json
import sys
import os
import time
import importlib
import httpx
from unittest.mock import MagicMock, AsyncMock

# 프로젝트 루트를 sys.path에 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# hyphenated 패키지명은 importlib으로 로드
_a2a_mod = importlib.import_module("genai-fundamentals.api.a2a_server")
_models_mod = importlib.import_module("genai-fundamentals.api.models")
_agent_svc_mod = importlib.import_module("genai-fundamentals.api.agent.service")

AGENT_CARD = _a2a_mod.AGENT_CARD
GraphRAGAgentExecutor = _a2a_mod.GraphRAGAgentExecutor
TokenUsage = _models_mod.TokenUsage
AgentResult = _agent_svc_mod.AgentResult


# =============================================================================
# Fixtures
# =============================================================================

A2A_PORT = 19000  # 테스트 전용 포트 (충돌 방지)


@pytest.fixture(scope="class")
def a2a_server():
    """A2A 서버 프로세스 시작/종료 픽스처 (클래스 단위)"""
    process = subprocess.Popen(
        [sys.executable, "-m", "genai-fundamentals.api.a2a_server", "--port", str(A2A_PORT)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    )

    # 서버 시작 대기
    max_wait = 15
    started = False
    for _ in range(max_wait * 2):
        time.sleep(0.5)
        try:
            resp = httpx.get(f"http://localhost:{A2A_PORT}/.well-known/agent.json", timeout=2)
            if resp.status_code == 200:
                started = True
                break
        except (httpx.ConnectError, httpx.TimeoutException):
            continue

    if not started:
        process.terminate()
        process.wait(timeout=5)
        pytest.skip("A2A server failed to start")

    yield process

    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()


@pytest.fixture
def a2a_url():
    """A2A 서버 URL"""
    return f"http://localhost:{A2A_PORT}"


def send_a2a_request(url: str, method: str, params: dict = None, request_id: str = "1", timeout: float = 30) -> dict:
    """A2A JSON-RPC 요청 전송 헬퍼"""
    payload = {
        "jsonrpc": "2.0",
        "id": request_id,
        "method": method,
    }
    if params:
        payload["params"] = params

    resp = httpx.post(url + "/", json=payload, timeout=timeout)
    return resp.json()


# =============================================================================
# Mock Tests (API 호출 없음)
# =============================================================================

class TestA2AServerMock:
    """A2A 서버 Mock 테스트 (외부 의존성 없음)"""

    def test_agent_card_structure(self):
        """AgentCard 구조 검증"""
        assert AGENT_CARD.name == "GraphRAG Agent"
        assert AGENT_CARD.version == "1.0.0"
        assert "text/plain" in AGENT_CARD.default_input_modes
        assert "application/json" in AGENT_CARD.default_output_modes
        assert AGENT_CARD.capabilities.streaming is False
        assert AGENT_CARD.capabilities.push_notifications is False

    def test_agent_card_skills(self):
        """AgentCard 스킬 목록 검증"""
        skills = {s.id: s for s in AGENT_CARD.skills}
        assert "graphrag_agent" in skills
        assert len(skills) == 1  # Agent-only: graphrag_agent만 있음

        # graphrag_agent 스킬 검증
        agent_skill = skills["graphrag_agent"]
        assert "neo4j" in agent_skill.tags
        assert "react" in agent_skill.tags
        assert len(agent_skill.examples) >= 2

    def test_executor_extract_text(self):
        """텍스트 추출 로직 검증"""
        from a2a.types import Part, TextPart

        executor = GraphRAGAgentExecutor()

        # TextPart가 있는 메시지
        msg = MagicMock()
        msg.parts = [
            Part(root=TextPart(text="Hello")),
            Part(root=TextPart(text="World")),
        ]
        assert executor._extract_text(msg) == "Hello World"

        # 빈 메시지
        msg_empty = MagicMock()
        msg_empty.parts = []
        assert executor._extract_text(msg_empty) == ""

        # None 메시지
        assert executor._extract_text(None) == ""

    @pytest.mark.asyncio
    async def test_executor_agent_mock(self):
        """Agent 실행 Mock 테스트 (모든 쿼리는 Agent를 통해 처리됨)"""
        from a2a.types import Part, TextPart

        executor = GraphRAGAgentExecutor()

        # Mock agent service
        mock_agent = MagicMock()
        mock_result = AgentResult(
            answer="Agent answer",
            thoughts=["thinking..."],
            tool_calls=[{"name": "cypher_query", "args": {}}],
            tool_results=[],
            iterations=2,
            token_usage=TokenUsage(total_tokens=500, prompt_tokens=400, completion_tokens=100, total_cost=0.005),
        )
        mock_agent.query_async = AsyncMock(return_value=mock_result)
        executor._agent_service = mock_agent

        # Mock context
        ctx = MagicMock()
        ctx.message.parts = [Part(root=TextPart(text="test query"))]
        ctx.context_id = "agent-ctx"
        ctx.task_id = "agent-task"

        # Mock event queue
        event_queue = MagicMock()
        event_queue.enqueue_event = AsyncMock()

        await executor.execute(ctx, event_queue)

        # Agent 서비스 호출 확인
        mock_agent.query_async.assert_called_once_with(
            query_text="test query", session_id="agent-ctx"
        )

        # 이벤트 큐에 응답과 완료 상태가 전송되었는지 확인
        assert event_queue.enqueue_event.call_count == 2

    @pytest.mark.asyncio
    async def test_executor_error_handling(self):
        """에러 처리 Mock 테스트"""
        from a2a.types import Part, TextPart

        executor = GraphRAGAgentExecutor()

        # Mock agent service that raises
        mock_agent = MagicMock()
        mock_agent.query_async = AsyncMock(side_effect=Exception("DB connection failed"))
        executor._agent_service = mock_agent

        ctx = MagicMock()
        ctx.message.parts = [Part(root=TextPart(text="query"))]
        ctx.context_id = "err-ctx"
        ctx.task_id = "err-task"

        event_queue = MagicMock()
        event_queue.enqueue_event = AsyncMock()

        await executor.execute(ctx, event_queue)

        # 에러 메시지 + failed 상태 전송 확인
        assert event_queue.enqueue_event.call_count == 2

    @pytest.mark.asyncio
    async def test_executor_empty_message(self):
        """빈 메시지 에러 처리 테스트"""
        executor = GraphRAGAgentExecutor()

        ctx = MagicMock()
        ctx.message.parts = []
        ctx.context_id = "empty-ctx"
        ctx.task_id = "empty-task"

        event_queue = MagicMock()
        event_queue.enqueue_event = AsyncMock()

        await executor.execute(ctx, event_queue)

        # 에러 응답 전송 확인
        assert event_queue.enqueue_event.call_count == 2

    @pytest.mark.asyncio
    async def test_executor_cancel(self):
        """태스크 취소 테스트"""
        executor = GraphRAGAgentExecutor()

        ctx = MagicMock()
        ctx.task_id = "cancel-task"
        ctx.context_id = "cancel-ctx"

        event_queue = MagicMock()
        event_queue.enqueue_event = AsyncMock()

        await executor.cancel(ctx, event_queue)

        # canceled 상태 전송 확인
        event_queue.enqueue_event.assert_called_once()


# =============================================================================
# Integration Tests (A2A 서버 + Neo4j + OpenAI 필요)
# =============================================================================

@pytest.mark.integration
class TestA2AServerIntegration:
    """A2A 서버 통합 테스트 (실제 서버 구동)"""

    def test_agent_card_endpoint(self, a2a_server, a2a_url):
        """AgentCard 엔드포인트 테스트"""
        resp = httpx.get(f"{a2a_url}/.well-known/agent.json", timeout=5)
        assert resp.status_code == 200

        card = resp.json()
        assert card["name"] == "GraphRAG Agent"
        assert card["version"] == "1.0.0"
        assert "skills" in card
        assert len(card["skills"]) == 1  # Agent-only: graphrag_agent만 있음

        skill_ids = [s["id"] for s in card["skills"]]
        assert "graphrag_agent" in skill_ids

    def test_query_basic(self, a2a_server, a2a_url):
        """기본 쿼리 테스트 (message/send) - Agent를 통해 처리"""
        result = send_a2a_request(
            a2a_url,
            method="message/send",
            params={
                "message": {
                    "messageId": "test-001",
                    "role": "user",
                    "parts": [{"kind": "text", "text": "Which actors appeared in The Matrix?"}],
                }
            },
            timeout=120,
        )

        assert "result" in result, f"Unexpected response: {result}"
        msg = result["result"]

        # 텍스트 파트 확인
        text_parts = [p for p in msg["parts"] if p["kind"] == "text"]
        assert len(text_parts) >= 1
        answer = text_parts[0]["text"]
        assert len(answer) > 0

        # 데이터 파트 확인 (Agent 응답)
        data_parts = [p for p in msg["parts"] if p["kind"] == "data"]
        assert len(data_parts) >= 1
        data = data_parts[0]["data"]
        assert "iterations" in data
        assert "token_usage" in data

    def test_query_semantic(self, a2a_server, a2a_url):
        """시맨틱 검색 쿼리 테스트"""
        result = send_a2a_request(
            a2a_url,
            method="message/send",
            params={
                "message": {
                    "messageId": "test-002",
                    "role": "user",
                    "parts": [{"kind": "text", "text": "Find me movies about toys coming alive"}],
                }
            },
            timeout=120,
        )

        assert "result" in result
        data_parts = [p for p in result["result"]["parts"] if p["kind"] == "data"]
        assert len(data_parts) >= 1
        data = data_parts[0]["data"]
        assert "iterations" in data

    def test_query_general(self, a2a_server, a2a_url):
        """일반 쿼리 테스트"""
        result = send_a2a_request(
            a2a_url,
            method="message/send",
            params={
                "message": {
                    "messageId": "test-003",
                    "role": "user",
                    "parts": [{"kind": "text", "text": "안녕하세요"}],
                }
            },
            timeout=120,
        )

        assert "result" in result
        text_parts = [p for p in result["result"]["parts"] if p["kind"] == "text"]
        assert len(text_parts) >= 1

    def test_query_complex(self, a2a_server, a2a_url):
        """복잡한 쿼리 테스트"""
        result = send_a2a_request(
            a2a_url,
            method="message/send",
            params={
                "message": {
                    "messageId": "test-004",
                    "role": "user",
                    "parts": [{"kind": "text", "text": "What genre is Toy Story?"}],
                }
            },
            timeout=120,
        )

        assert "result" in result, f"Unexpected response: {result}"
        msg = result["result"]

        # 텍스트 응답 확인
        text_parts = [p for p in msg["parts"] if p["kind"] == "text"]
        assert len(text_parts) >= 1

        # Agent 데이터 파트 확인
        data_parts = [p for p in msg["parts"] if p["kind"] == "data"]
        assert len(data_parts) >= 1
        data = data_parts[0]["data"]
        assert "iterations" in data
        assert "token_usage" in data

    def test_query_token_usage(self, a2a_server, a2a_url):
        """토큰 사용량 추적 테스트"""
        result = send_a2a_request(
            a2a_url,
            method="message/send",
            params={
                "message": {
                    "messageId": "test-005",
                    "role": "user",
                    "parts": [{"kind": "text", "text": "Who directed The Matrix?"}],
                }
            },
            timeout=60,
        )

        assert "result" in result
        data_parts = [p for p in result["result"]["parts"] if p["kind"] == "data"]
        data = data_parts[0]["data"]

        assert "token_usage" in data
        usage = data["token_usage"]
        assert usage["total_tokens"] > 0
        assert usage["prompt_tokens"] > 0
        assert usage["completion_tokens"] > 0
        assert usage["total_cost"] >= 0

    def test_context_id_preserved(self, a2a_server, a2a_url):
        """contextId가 응답에 보존되는지 테스트"""
        result = send_a2a_request(
            a2a_url,
            method="message/send",
            params={
                "message": {
                    "messageId": "test-006",
                    "role": "user",
                    "parts": [{"kind": "text", "text": "Hello"}],
                }
            },
            timeout=60,
        )

        assert "result" in result
        msg = result["result"]
        assert "contextId" in msg
        assert "taskId" in msg


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
