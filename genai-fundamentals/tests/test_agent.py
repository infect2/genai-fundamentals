"""
ReAct Agent Tests

ReAct Agent의 기능을 테스트합니다.

실행 방법:
    # 모든 Agent 테스트 실행
    pytest genai-fundamentals/tests/test_agent.py -v

    # Mock 테스트만 실행 (API 호출 없음)
    pytest genai-fundamentals/tests/test_agent.py -v -k "mock"

    # 통합 테스트 (API 호출 필요)
    pytest genai-fundamentals/tests/test_agent.py -v -k "integration"
"""

import sys
import os
import importlib

# 프로젝트 루트를 sys.path에 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pytest
from unittest.mock import Mock, patch, MagicMock
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage

# hyphenated 패키지명은 importlib으로 로드
_state_mod = importlib.import_module("genai-fundamentals.api.agent.state")
_prompts_mod = importlib.import_module("genai-fundamentals.api.agent.prompts")
_service_mod = importlib.import_module("genai-fundamentals.api.agent.service")

AgentState = _state_mod.AgentState
ToolResult = _state_mod.ToolResult
REACT_SYSTEM_PROMPT = _prompts_mod.REACT_SYSTEM_PROMPT
TOOL_DESCRIPTIONS = _prompts_mod.TOOL_DESCRIPTIONS
AgentResult = _service_mod.AgentResult


class TestAgentState:
    """AgentState TypedDict 테스트"""

    def test_agent_state_creation(self):
        """AgentState 생성 테스트"""
        state: AgentState = {
            "messages": [HumanMessage(content="test query")],
            "session_id": "test-session",
            "tool_results": [],
            "iteration": 0,
            "final_answer": None
        }

        assert len(state["messages"]) == 1
        assert state["session_id"] == "test-session"
        assert state["iteration"] == 0
        assert state["final_answer"] is None

    def test_tool_result_creation(self):
        """ToolResult 생성 테스트"""
        result: ToolResult = {
            "tool_name": "cypher_query",
            "tool_input": {"query": "test"},
            "result": "success",
            "success": True
        }

        assert result["tool_name"] == "cypher_query"
        assert result["success"] is True


class TestAgentPrompts:
    """Agent 프롬프트 테스트"""

    def test_system_prompt_contains_tools(self):
        """시스템 프롬프트에 도구 설명 포함 확인"""
        assert "cypher_query" in REACT_SYSTEM_PROMPT
        assert "vector_search" in REACT_SYSTEM_PROMPT
        assert "hybrid_search" in REACT_SYSTEM_PROMPT
        assert "get_schema" in REACT_SYSTEM_PROMPT

    def test_system_prompt_contains_knowledge_graph_context(self):
        """시스템 프롬프트에 지식 그래프 컨텍스트 포함 확인"""
        assert "knowledge graph" in REACT_SYSTEM_PROMPT.lower() or "ontology" in REACT_SYSTEM_PROMPT.lower()
        assert "entity" in REACT_SYSTEM_PROMPT.lower() or "entities" in REACT_SYSTEM_PROMPT.lower()

    def test_tool_descriptions_complete(self):
        """모든 도구 설명이 있는지 확인"""
        expected_tools = ["cypher_query", "vector_search", "hybrid_search", "get_schema"]
        for tool in expected_tools:
            assert tool in TOOL_DESCRIPTIONS


class TestAgentResult:
    """AgentResult dataclass 테스트"""

    def test_agent_result_creation(self):
        """AgentResult 생성 테스트"""
        result = AgentResult(
            answer="Test answer",
            thoughts=["Thought 1", "Thought 2"],
            tool_calls=[{"name": "cypher_query", "args": {"query": "test"}}],
            tool_results=[{"tool_name": "cypher_query", "result": "data"}],
            iterations=3
        )

        assert result.answer == "Test answer"
        assert len(result.thoughts) == 2
        assert len(result.tool_calls) == 1
        assert result.iterations == 3


class TestAgentToolsMock:
    """Agent Tools Mock 테스트 (API 호출 없음)"""

    def test_create_agent_tools_returns_list(self):
        """create_agent_tools가 리스트를 반환하는지 확인"""
        _tools_mod = importlib.import_module("genai-fundamentals.api.agent.tools")
        create_agent_tools = _tools_mod.create_agent_tools

        # Mock 서비스 생성
        mock_service = Mock()
        mock_service.execute_cypher_rag.return_value = Mock(
            answer="test", cypher="MATCH", context=[]
        )
        mock_service.execute_vector_rag.return_value = Mock(
            answer="test", context=[]
        )
        mock_service.execute_hybrid_rag.return_value = Mock(
            answer="test", cypher="MATCH", context=[]
        )
        mock_service.get_schema.return_value = "schema"

        tools = create_agent_tools(mock_service)

        assert isinstance(tools, list)
        assert len(tools) == 5  # cypher_query, vector_search, hybrid_search, get_schema, user_memory


class TestAgentServiceMock:
    """AgentService Mock 테스트 (API 호출 없음)"""

    def test_extract_result_basic(self):
        """_extract_result 기본 테스트"""
        AgentService = importlib.import_module("genai-fundamentals.api.agent.service").AgentService

        # AgentService 인스턴스 생성 없이 메서드만 테스트
        service = AgentService.__new__(AgentService)

        final_state = {
            "messages": [
                HumanMessage(content="test query"),
                AIMessage(content="Final answer here")
            ],
            "tool_results": [],
            "iteration": 2
        }

        result = service._extract_result(final_state)

        assert result.answer == "Final answer here"
        assert result.iterations == 2

    def test_extract_result_with_tool_calls(self):
        """_extract_result 도구 호출 포함 테스트"""
        AgentService = importlib.import_module("genai-fundamentals.api.agent.service").AgentService

        service = AgentService.__new__(AgentService)

        # Tool call이 있는 AIMessage
        ai_msg_with_tool = AIMessage(content="")
        ai_msg_with_tool.tool_calls = [
            {"name": "cypher_query", "args": {"query": "test"}}
        ]

        final_state = {
            "messages": [
                HumanMessage(content="test query"),
                ai_msg_with_tool,
                ToolMessage(content="tool result", tool_call_id="1"),
                AIMessage(content="Final answer after tool")
            ],
            "tool_results": [{"tool_name": "cypher_query", "result": "data"}],
            "iteration": 3
        }

        result = service._extract_result(final_state)

        assert result.answer == "Final answer after tool"
        assert len(result.tool_calls) == 1
        assert result.tool_calls[0]["name"] == "cypher_query"


class TestAgentGraphMock:
    """Agent Graph Mock 테스트"""

    def test_max_iterations_constant(self):
        """MAX_ITERATIONS 상수 확인"""
        _graph_mod = importlib.import_module("genai-fundamentals.api.agent.graph")
        MAX_ITERATIONS = _graph_mod.MAX_ITERATIONS

        assert MAX_ITERATIONS == 10

    def test_create_agent_graph(self):
        """create_agent_graph 함수 테스트"""
        _graph_mod = importlib.import_module("genai-fundamentals.api.agent.graph")
        create_agent_graph = _graph_mod.create_agent_graph

        # 실제 서비스 없이 그래프 생성 확인 (기본 구조 테스트)
        mock_service = Mock()
        mock_service.get_schema.return_value = "test schema"

        # create_agent_graph가 실행 가능한지 확인
        # 실제 LLM 호출 없이 그래프 구조만 확인
        graph = create_agent_graph(mock_service)

        assert graph is not None


@pytest.mark.integration
class TestAgentIntegration:
    """Agent 통합 테스트 (실제 API 호출)

    주의: 이 테스트는 OpenAI API와 Neo4j를 호출합니다.
    환경변수가 설정되어 있어야 합니다.
    """

    @pytest.fixture
    def agent_service(self):
        """실제 AgentService 인스턴스"""
        from dotenv import load_dotenv
        load_dotenv()

        GraphRAGService = importlib.import_module("genai-fundamentals.api.graphrag_service").GraphRAGService
        AgentService = importlib.import_module("genai-fundamentals.api.agent.service").AgentService

        graphrag_service = GraphRAGService()
        return AgentService(graphrag_service)

    def test_simple_query(self, agent_service):
        """단순 쿼리 통합 테스트"""
        result = agent_service.query("What actors appeared in The Matrix?")

        assert result.answer is not None
        assert len(result.answer) > 0
        assert result.iterations > 0

    def test_query_uses_tools(self, agent_service):
        """도구를 사용하는 쿼리 테스트"""
        result = agent_service.query("Who directed The Godfather?")

        # 도구가 호출되었거나 직접 답변이 있어야 함
        assert result.answer is not None or len(result.tool_calls) > 0

    @pytest.mark.asyncio
    async def test_async_query(self, agent_service):
        """비동기 쿼리 테스트"""
        result = await agent_service.query_async("List some actors from Toy Story")

        assert result.answer is not None
        assert result.iterations > 0

    def test_complex_query(self, agent_service):
        """복잡한 쿼리 테스트 (multi-step reasoning 필요)"""
        result = agent_service.query(
            "Find movies similar to The Matrix that have action elements"
        )

        assert result.answer is not None
        # 복잡한 쿼리는 여러 번의 반복이 필요할 수 있음
        assert result.iterations >= 1


@pytest.mark.integration
class TestAgentAPIIntegration:
    """Agent REST API 통합 테스트"""

    @pytest.fixture
    def client(self):
        """FastAPI TestClient"""
        from fastapi.testclient import TestClient
        from dotenv import load_dotenv
        load_dotenv()

        app = importlib.import_module("genai-fundamentals.api.server").app
        return TestClient(app)

    def test_agent_query_endpoint(self, client):
        """POST /agent/query 엔드포인트 테스트"""
        response = client.post(
            "/agent/query",
            json={
                "query": "What is The Matrix about?",
                "session_id": "test-session"
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert "answer" in data
        assert "iterations" in data

    def test_agent_query_with_stream_false(self, client):
        """POST /agent/query stream=false 테스트"""
        response = client.post(
            "/agent/query",
            json={
                "query": "Who directed Forrest Gump?",
                "stream": False
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert data["answer"] is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
