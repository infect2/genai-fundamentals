"""
Base Domain Agent Module

도메인 에이전트의 추상 기본 클래스를 정의합니다.
모든 도메인 에이전트(WMS, TMS, FMS, TAP)는 이 클래스를 상속받습니다.

Usage:
    from genai_fundamentals.api.multi_agents.base import BaseDomainAgent, DomainType

    class TMSAgent(BaseDomainAgent):
        domain = DomainType.TMS
        description = "운송 관리 시스템 전문 에이전트"

        def get_tools(self) -> List[BaseTool]:
            return [shipment_status, route_optimization]

        def get_system_prompt(self) -> str:
            return TMS_SYSTEM_PROMPT

        def get_schema_subset(self) -> str:
            return get_tms_schema()
"""

import asyncio
import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Any, Dict, AsyncGenerator

from langchain_core.tools import BaseTool
from langchain_core.messages import HumanMessage, AIMessage

from ..models import TokenUsage

logger = logging.getLogger(__name__)


# =============================================================================
# 도메인 타입 정의
# =============================================================================

class DomainType(Enum):
    """
    도메인 에이전트 유형

    각 도메인은 물류 시스템의 특정 영역을 담당합니다.
    """
    WMS = "wms"      # Warehouse Management System (창고 관리)
    TMS = "tms"      # Transportation Management System (운송 관리)
    FMS = "fms"      # Fleet Management System (차량 관리)
    TAP = "tap"      # TAP! Service (사용자 호출 서비스)
    UNKNOWN = "unknown"

    @classmethod
    def from_string(cls, value: str) -> "DomainType":
        """문자열에서 DomainType 변환"""
        try:
            return cls(value.lower())
        except ValueError:
            return cls.UNKNOWN


# =============================================================================
# 도메인 라우팅 결정
# =============================================================================

@dataclass
class DomainRouteDecision:
    """
    도메인 라우팅 결정 결과

    Orchestrator가 사용자 쿼리를 분석하여 어떤 도메인 에이전트로
    라우팅할지 결정한 결과를 담습니다.

    Attributes:
        domain: 주요 도메인 (primary)
        confidence: 라우팅 신뢰도 (0.0 ~ 1.0)
        reasoning: 라우팅 결정 이유
        requires_cross_domain: 크로스 도메인 처리 필요 여부
        secondary_domains: 보조 도메인 목록 (크로스 도메인 시)
    """
    domain: DomainType
    confidence: float
    reasoning: str
    requires_cross_domain: bool = False
    secondary_domains: List[DomainType] = field(default_factory=list)

    def __post_init__(self):
        """검증"""
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"confidence must be between 0.0 and 1.0, got {self.confidence}")


# =============================================================================
# 도메인 에이전트 결과
# =============================================================================

@dataclass
class DomainAgentResult:
    """
    도메인 에이전트 실행 결과

    Attributes:
        answer: 최종 답변
        domain: 처리한 도메인
        thoughts: 추론 과정 (thinking steps)
        tool_calls: 호출된 도구 목록
        tool_results: 도구 실행 결과 목록
        iterations: 총 반복 횟수
        token_usage: LLM 토큰 사용량
        metadata: 추가 메타데이터
    """
    answer: str
    domain: DomainType
    thoughts: List[str] = field(default_factory=list)
    tool_calls: List[dict] = field(default_factory=list)
    tool_results: List[dict] = field(default_factory=list)
    iterations: int = 0
    token_usage: Optional[TokenUsage] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


# =============================================================================
# 도메인 에이전트 추상 기본 클래스
# =============================================================================

class BaseDomainAgent(ABC):
    """
    도메인 에이전트 추상 기본 클래스

    모든 도메인 에이전트(WMS, TMS, FMS, TAP)는 이 클래스를 상속받아
    도메인별 도구, 프롬프트, 스키마를 구현합니다.

    기존 AgentService의 ReAct 패턴을 재사용하여
    도메인 특화된 에이전트를 구현할 수 있습니다.

    Subclass Requirements:
        - domain: DomainType 클래스 변수
        - description: 에이전트 설명
        - get_tools(): 도메인 전용 도구 반환
        - get_system_prompt(): 도메인 시스템 프롬프트 반환
        - get_schema_subset(): 도메인 관련 온톨로지 스키마 반환
    """

    # 클래스 변수 (서브클래스에서 오버라이드)
    domain: DomainType = DomainType.UNKNOWN
    description: str = "Base domain agent"

    def __init__(self, graphrag_service=None, model_name: Optional[str] = None):
        """
        도메인 에이전트 초기화

        Args:
            graphrag_service: GraphRAGService 인스턴스 (공유 서비스)
            model_name: 사용할 LLM 모델명
        """
        self._graphrag_service = graphrag_service
        self._model_name = model_name
        self._graph = None  # Lazy initialization

    @abstractmethod
    def get_tools(self) -> List[BaseTool]:
        """
        도메인 전용 도구 목록 반환

        Returns:
            BaseTool 객체 리스트
        """
        pass

    @abstractmethod
    def get_system_prompt(self) -> str:
        """
        도메인 시스템 프롬프트 반환

        Returns:
            시스템 프롬프트 문자열
        """
        pass

    @abstractmethod
    def get_schema_subset(self) -> str:
        """
        도메인 관련 온톨로지 스키마 부분집합 반환

        TBox(스키마)와 도메인별 제약 조건을 반환합니다.

        Returns:
            스키마 문자열 (Cypher 형식 또는 자연어)
        """
        pass

    def get_keywords(self) -> List[str]:
        """
        도메인 키워드 목록 반환

        라우팅 시 키워드 매칭에 사용됩니다.
        서브클래스에서 오버라이드할 수 있습니다.

        Returns:
            키워드 문자열 리스트
        """
        return []

    def _create_graph(self):
        """
        LangGraph StateGraph 생성 (Lazy initialization)

        기존 AgentService의 create_agent_graph를 활용하되,
        도메인 전용 도구와 프롬프트를 사용합니다.
        """
        if self._graph is not None:
            return self._graph

        from .graph_factory import create_domain_agent_graph

        self._graph = create_domain_agent_graph(
            domain_agent=self,
            graphrag_service=self._graphrag_service,
            model_name=self._model_name
        )
        return self._graph

    def query(
        self,
        query_text: str,
        session_id: str = "default",
        context: Optional[Dict[str, Any]] = None
    ) -> DomainAgentResult:
        """
        도메인 쿼리 실행 (동기 방식)

        ReAct 패턴을 사용하여 도메인 특화 쿼리를 처리합니다.

        Args:
            query_text: 사용자 질문
            session_id: 세션 ID
            context: 추가 컨텍스트 (크로스 도메인 시 이전 결과 등)

        Returns:
            DomainAgentResult 객체
        """
        from ...tools.llm_provider import get_token_tracker

        graph = self._create_graph()

        # 컨텍스트 메시지 생성
        context_msg = ""
        if context:
            context_msg = f"\n\n[Previous Context]\n{context}"

        # 초기 상태 설정
        initial_state = {
            "messages": [HumanMessage(content=query_text + context_msg)],
            "session_id": session_id,
            "tool_results": [],
            "iteration": 0,
            "final_answer": None
        }

        # 그래프 실행
        with get_token_tracker() as cb:
            final_state = graph.invoke(initial_state)

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
        session_id: str = "default",
        context: Optional[Dict[str, Any]] = None
    ) -> DomainAgentResult:
        """
        도메인 쿼리 실행 (비동기 방식)

        Args:
            query_text: 사용자 질문
            session_id: 세션 ID
            context: 추가 컨텍스트

        Returns:
            DomainAgentResult 객체
        """
        from ...tools.llm_provider import get_token_tracker

        graph = self._create_graph()

        # 컨텍스트 메시지 생성
        context_msg = ""
        if context:
            context_msg = f"\n\n[Previous Context]\n{context}"

        # 초기 상태 설정
        initial_state = {
            "messages": [HumanMessage(content=query_text + context_msg)],
            "session_id": session_id,
            "tool_results": [],
            "iteration": 0,
            "final_answer": None
        }

        # 비동기 그래프 실행
        with get_token_tracker() as cb:
            final_state = await graph.ainvoke(initial_state)

        # 결과 추출
        result = self._extract_result(final_state)
        result.token_usage = TokenUsage(
            total_tokens=cb.total_tokens,
            prompt_tokens=cb.prompt_tokens,
            completion_tokens=cb.completion_tokens,
            total_cost=cb.total_cost
        )

        return result

    def _extract_result(self, final_state: dict) -> DomainAgentResult:
        """
        최종 상태에서 결과 추출

        Args:
            final_state: LangGraph 실행 후 최종 상태

        Returns:
            DomainAgentResult 객체
        """
        messages = final_state.get("messages", [])
        tool_results = final_state.get("tool_results", [])
        iterations = final_state.get("iteration", 0)

        # 최종 답변 추출
        answer = ""
        thoughts = []
        tool_calls = []

        for msg in messages:
            if isinstance(msg, AIMessage):
                if msg.tool_calls:
                    for tc in msg.tool_calls:
                        tool_calls.append({
                            "name": tc.get("name", ""),
                            "args": tc.get("args", {})
                        })
                elif msg.content:
                    answer = msg.content
                    thoughts.append(msg.content)

        return DomainAgentResult(
            answer=answer,
            domain=self.domain,
            thoughts=thoughts,
            tool_calls=tool_calls,
            tool_results=tool_results,
            iterations=iterations
        )

    async def query_stream(
        self,
        query_text: str,
        session_id: str = "default",
        context: Optional[Dict[str, Any]] = None
    ) -> AsyncGenerator[str, None]:
        """
        도메인 쿼리 스트리밍 실행

        SSE 형식으로 토큰, 도구 호출, 도구 결과를 스트리밍합니다.

        Args:
            query_text: 사용자 질문
            session_id: 세션 ID
            context: 추가 컨텍스트

        Yields:
            SSE 형식 문자열
        """
        from ...tools.llm_provider import get_token_tracker

        graph = self._create_graph()

        # 컨텍스트 메시지 생성
        context_msg = ""
        if context:
            context_msg = f"\n\n[Previous Context]\n{context}"

        initial_state = {
            "messages": [HumanMessage(content=query_text + context_msg)],
            "session_id": session_id,
            "tool_results": [],
            "iteration": 0,
            "final_answer": None
        }

        final_answer = ""
        tool_calls_sent = set()
        tool_calls_list = []
        tool_results_list = []

        with get_token_tracker() as cb:
            async for event in graph.astream_events(initial_state, version="v2"):
                event_type = event.get("event", "")
                event_data = event.get("data", {})

                if event_type == "on_chat_model_stream":
                    chunk = event_data.get("chunk")
                    if chunk and hasattr(chunk, "content") and chunk.content:
                        yield f"data: {json.dumps({'type': 'token', 'content': chunk.content})}\n\n"

                elif event_type == "on_chat_model_end":
                    output = event_data.get("output")
                    if output and hasattr(output, "tool_calls") and output.tool_calls:
                        for tc in output.tool_calls:
                            tc_id = tc.get("id", "")
                            if tc_id not in tool_calls_sent:
                                tool_calls_sent.add(tc_id)
                                tc_info = {"name": tc.get("name", ""), "args": tc.get("args", {})}
                                tool_calls_list.append(tc_info)
                                yield f"data: {json.dumps({'type': 'tool_call', 'tool': tc_info['name'], 'input': tc_info['args']})}\n\n"
                    elif output and hasattr(output, "content") and output.content:
                        final_answer = output.content

                elif event_type == "on_tool_end":
                    output = event_data.get("output")
                    if output:
                        if hasattr(output, "content"):
                            result_content = output.content
                        elif isinstance(output, str):
                            result_content = output
                        else:
                            result_content = str(output)
                        if len(result_content) > 500:
                            result_content = result_content[:500] + "..."
                        tool_results_list.append({"result": result_content})
                        yield f"data: {json.dumps({'type': 'tool_result', 'result': result_content})}\n\n"

        # 최종 완료 데이터 (도메인 정보 포함)
        done_data = {
            "type": "done",
            "final_answer": final_answer,
            "domain": self.domain.value,
            "tool_calls": tool_calls_list,
            "tool_results": tool_results_list,
            "token_usage": {
                "total_tokens": cb.total_tokens,
                "prompt_tokens": cb.prompt_tokens,
                "completion_tokens": cb.completion_tokens,
                "total_cost": cb.total_cost
            }
        }
        yield f"data: {json.dumps(done_data)}\n\n"

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(domain={self.domain.value}, description='{self.description}')"
