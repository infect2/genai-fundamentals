"""
Agent State Module

LangGraph에서 사용하는 AgentState 스키마를 정의합니다.
TypedDict를 사용하여 상태의 타입 안전성을 보장합니다.
"""

from typing import Annotated, Sequence, Optional, List
from typing_extensions import TypedDict
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class ToolResult(TypedDict):
    """도구 실행 결과를 담는 TypedDict"""
    tool_name: str
    tool_input: dict
    result: str
    success: bool


class AgentState(TypedDict):
    """
    ReAct Agent의 상태 스키마

    LangGraph StateGraph에서 사용되며, 각 노드 간에
    상태를 전달하는 데 사용됩니다.

    Attributes:
        messages: 대화 메시지 시퀀스 (HumanMessage, AIMessage, ToolMessage 등)
                 add_messages reducer를 사용하여 자동으로 메시지가 추가됨
        session_id: 세션 식별자 (대화 컨텍스트 유지용)
        tool_results: 도구 실행 결과 목록 (디버깅/로깅용)
        iteration: 현재 reasoning loop 반복 횟수 (무한 루프 방지)
        final_answer: 최종 응답 (있으면 루프 종료)
    """
    messages: Annotated[Sequence[BaseMessage], add_messages]
    session_id: str
    tool_results: List[ToolResult]
    iteration: int
    final_answer: Optional[str]
