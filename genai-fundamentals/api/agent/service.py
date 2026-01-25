"""
Agent Service Module

AgentService는 ReAct Agent의 통합 인터페이스를 제공합니다.
기존 GraphRAGService와 LangGraph Agent를 연결합니다.
"""

import json
import asyncio
from dataclasses import dataclass
from typing import Optional, List, AsyncGenerator, Any

from langchain_core.messages import HumanMessage, AIMessage, ToolMessage

from ...tools.llm_provider import get_token_tracker

from .graph import create_agent_graph
from .state import AgentState
from ..models import TokenUsage


@dataclass
class AgentResult:
    """
    Agent 실행 결과를 담는 데이터 클래스

    Attributes:
        answer: 최종 답변
        thoughts: Agent의 추론 과정 (thinking steps)
        tool_calls: 호출된 도구 목록
        tool_results: 도구 실행 결과 목록
        iterations: 총 반복 횟수
        token_usage: LLM 토큰 사용량
    """
    answer: str
    thoughts: List[str]
    tool_calls: List[dict]
    tool_results: List[dict]
    iterations: int
    token_usage: Optional[TokenUsage] = None


class AgentService:
    """
    ReAct Agent 서비스 클래스

    LangGraph 기반 ReAct Agent를 사용하여
    multi-step reasoning을 통해 복잡한 쿼리를 처리합니다.

    사용 예:
        from genai_fundamentals.api.graphrag_service import GraphRAGService
        from genai_fundamentals.api.agent import AgentService

        ontology_service = GraphRAGService()
        agent_service = AgentService(ontology_service)
        result = agent_service.query("Find entities connected to X with similar properties")
        print(result.answer)
    """

    def __init__(
        self,
        graphrag_service,
        model_name: Optional[str] = None
    ):
        """
        AgentService 초기화

        Args:
            graphrag_service: GraphRAGService 인스턴스
            model_name: Agent에서 사용할 LLM 모델 (기본값: 프로바이더별 환경변수)
        """
        self._graphrag_service = graphrag_service
        self._model_name = model_name
        self._graph = create_agent_graph(graphrag_service, model_name)

    def query(
        self,
        query_text: str,
        session_id: str = "default"
    ) -> AgentResult:
        """
        자연어 쿼리 실행 (동기 방식)

        ReAct Agent를 사용하여 multi-step reasoning으로
        복잡한 쿼리를 처리합니다.

        Args:
            query_text: 사용자 질문
            session_id: 세션 ID (기본값: "default")

        Returns:
            AgentResult 객체
        """
        # 초기 상태 설정
        initial_state: AgentState = {
            "messages": [HumanMessage(content=query_text)],
            "session_id": session_id,
            "tool_results": [],
            "iteration": 0,
            "final_answer": None
        }

        # 그래프 실행 (토큰 사용량 추적)
        with get_token_tracker() as cb:
            final_state = self._graph.invoke(initial_state)

        # 결과 추출
        result = self._extract_result(final_state)
        result.token_usage = TokenUsage(
            total_tokens=cb.total_tokens,
            prompt_tokens=cb.prompt_tokens,
            completion_tokens=cb.completion_tokens,
            total_cost=cb.total_cost
        )
        return result

    async def query_async(
        self,
        query_text: str,
        session_id: str = "default"
    ) -> AgentResult:
        """
        자연어 쿼리 실행 (비동기 방식)

        Args:
            query_text: 사용자 질문
            session_id: 세션 ID

        Returns:
            AgentResult 객체
        """
        # 초기 상태 설정
        initial_state: AgentState = {
            "messages": [HumanMessage(content=query_text)],
            "session_id": session_id,
            "tool_results": [],
            "iteration": 0,
            "final_answer": None
        }

        # 비동기 그래프 실행 (토큰 사용량 추적)
        with get_token_tracker() as cb:
            final_state = await self._graph.ainvoke(initial_state)

        # 결과 추출
        result = self._extract_result(final_state)
        result.token_usage = TokenUsage(
            total_tokens=cb.total_tokens,
            prompt_tokens=cb.prompt_tokens,
            completion_tokens=cb.completion_tokens,
            total_cost=cb.total_cost
        )
        return result

    async def query_stream(
        self,
        query_text: str,
        session_id: str = "default"
    ) -> AsyncGenerator[str, None]:
        """
        SSE 형식으로 스트리밍 응답 생성

        응답 순서:
        1. thought: Agent의 추론 과정
        2. tool_call: 도구 호출 정보
        3. tool_result: 도구 실행 결과
        4. token: 최종 답변 토큰
        5. done: 스트리밍 완료 (토큰 사용량 포함)

        Args:
            query_text: 사용자 질문
            session_id: 세션 ID

        Yields:
            SSE 형식 문자열
        """
        # 초기 상태 설정
        initial_state: AgentState = {
            "messages": [HumanMessage(content=query_text)],
            "session_id": session_id,
            "tool_results": [],
            "iteration": 0,
            "final_answer": None
        }

        final_answer = ""
        tool_calls_sent = set()

        # astream_events를 사용하여 실시간 이벤트 스트리밍 (토큰 사용량 추적)
        with get_token_tracker() as cb:
            async for event in self._graph.astream_events(initial_state, version="v2"):
                event_type = event.get("event", "")
                event_data = event.get("data", {})

                if event_type == "on_chat_model_stream":
                    # LLM 토큰 스트리밍
                    chunk = event_data.get("chunk")
                    if chunk and hasattr(chunk, "content") and chunk.content:
                        yield f"data: {json.dumps({'type': 'token', 'content': chunk.content})}\n\n"

                elif event_type == "on_chat_model_end":
                    # LLM 응답 완료
                    output = event_data.get("output")
                    if output and hasattr(output, "tool_calls") and output.tool_calls:
                        for tc in output.tool_calls:
                            tc_id = tc.get("id", "")
                            if tc_id not in tool_calls_sent:
                                tool_calls_sent.add(tc_id)
                                yield f"data: {json.dumps({'type': 'tool_call', 'tool': tc.get('name', ''), 'input': tc.get('args', {})})}\n\n"

                    elif output and hasattr(output, "content") and output.content:
                        final_answer = output.content

                elif event_type == "on_tool_end":
                    # 도구 실행 완료
                    output = event_data.get("output")
                    if output:
                        # ToolMessage에서 content 추출 (LangChain 메시지 객체인 경우)
                        if hasattr(output, "content"):
                            result_content = output.content
                        elif isinstance(output, str):
                            result_content = output
                        else:
                            result_content = str(output)
                        # 결과가 너무 길면 잘라냄
                        if len(result_content) > 500:
                            result_content = result_content[:500] + "..."
                        yield f"data: {json.dumps({'type': 'tool_result', 'result': result_content})}\n\n"

        # 완료 신호 (토큰 사용량 포함)
        done_data = {"type": "done", "final_answer": final_answer}
        done_data["token_usage"] = {
            "total_tokens": cb.total_tokens,
            "prompt_tokens": cb.prompt_tokens,
            "completion_tokens": cb.completion_tokens,
            "total_cost": cb.total_cost
        }
        yield f"data: {json.dumps(done_data)}\n\n"

    def _extract_result(self, final_state: dict) -> AgentResult:
        """
        최종 상태에서 결과를 추출합니다.

        Args:
            final_state: LangGraph 실행 후 최종 상태

        Returns:
            AgentResult 객체
        """
        messages = final_state.get("messages", [])
        tool_results = final_state.get("tool_results", [])
        iterations = final_state.get("iteration", 0)

        # 최종 답변 추출 (마지막 AIMessage)
        answer = ""
        thoughts = []
        tool_calls = []

        for msg in messages:
            if isinstance(msg, AIMessage):
                if msg.tool_calls:
                    # 도구 호출 기록
                    for tc in msg.tool_calls:
                        tool_calls.append({
                            "name": tc.get("name", ""),
                            "args": tc.get("args", {})
                        })
                elif msg.content:
                    # 최종 답변 또는 중간 추론
                    answer = msg.content
                    thoughts.append(msg.content)

        return AgentResult(
            answer=answer,
            thoughts=thoughts,
            tool_calls=tool_calls,
            tool_results=tool_results,
            iterations=iterations
        )


# =============================================================================
# 싱글톤 인스턴스 (선택적 사용)
# =============================================================================

_agent_service_instance: Optional[AgentService] = None


def get_agent_service(graphrag_service=None) -> AgentService:
    """
    AgentService 싱글톤 인스턴스 반환

    Args:
        graphrag_service: GraphRAGService 인스턴스 (최초 호출 시 필수)

    Returns:
        AgentService 인스턴스
    """
    global _agent_service_instance
    if _agent_service_instance is None:
        if graphrag_service is None:
            from ..graphrag_service import get_service
            graphrag_service = get_service()
        _agent_service_instance = AgentService(graphrag_service)
    return _agent_service_instance
