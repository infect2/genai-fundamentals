"""
Orchestrator State Module

Master Orchestrator의 상태 스키마를 정의합니다.
LangGraph StateGraph에서 사용됩니다.

Usage:
    from genai_fundamentals.api.multi_agents.orchestrator.state import OrchestratorState
"""

from typing import Annotated, Sequence, Optional, List, Dict, Any
from typing_extensions import TypedDict
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages

from ..base import DomainRouteDecision, DomainAgentResult


class ExecutionStep(TypedDict):
    """실행 계획 단계"""
    order: int
    domain: str
    action: str
    depends_on: Optional[int]


class ExecutionPlan(TypedDict):
    """실행 계획"""
    steps: List[ExecutionStep]
    parallel_groups: List[List[int]]


class OrchestratorState(TypedDict):
    """
    Master Orchestrator의 상태 스키마

    LangGraph StateGraph에서 사용되며, 각 노드 간에
    상태를 전달하는 데 사용됩니다.

    Attributes:
        messages: 대화 메시지 시퀀스
        session_id: 세션 식별자
        query: 원본 사용자 쿼리

        # 도메인 라우팅
        domain_decision: 도메인 라우팅 결정 결과
        execution_plan: 실행 계획 (크로스 도메인 시)

        # 멀티 에이전트 결과
        agent_results: 도메인별 실행 결과 {domain: DomainAgentResult}
        pending_domains: 아직 실행되지 않은 도메인 목록

        # 제어
        iteration: 현재 반복 횟수
        final_answer: 최종 응답 (있으면 종료)
        error: 오류 메시지
    """
    messages: Annotated[Sequence[BaseMessage], add_messages]
    session_id: str
    query: str

    # 도메인 라우팅
    domain_decision: Optional[Dict[str, Any]]  # DomainRouteDecision as dict
    execution_plan: Optional[Dict[str, Any]]   # ExecutionPlan as dict

    # 멀티 에이전트 결과
    agent_results: Dict[str, Dict[str, Any]]  # domain -> DomainAgentResult as dict
    pending_domains: List[str]

    # 제어
    iteration: int
    final_answer: Optional[str]
    error: Optional[str]
