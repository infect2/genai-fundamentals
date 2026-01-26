"""
Agent Graph Module

LangGraph를 사용한 ReAct Agent 그래프를 정의합니다.
Reason → Act → Observe 루프를 구현합니다.
"""

from typing import TYPE_CHECKING, List, Literal

from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, ToolMessage
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode

from ...tools.llm_provider import create_langchain_llm

from .state import AgentState
from .prompts import REACT_SYSTEM_PROMPT
from .tools import create_agent_tools
from ..config import get_config

if TYPE_CHECKING:
    from ..graphrag_service import GraphRAGService


def create_agent_graph(service: "GraphRAGService", model_name: str = None):
    """
    ReAct Agent 그래프를 생성합니다.

    Args:
        service: GraphRAGService 인스턴스
        model_name: 사용할 LLM 모델 (기본값: 프로바이더별 환경변수)

    Returns:
        컴파일된 LangGraph 그래프
    """
    # 도구 생성
    tools = create_agent_tools(service)

    # LLM 설정 (도구 바인딩)
    llm = create_langchain_llm(model_name=model_name, temperature=0)
    llm_with_tools = llm.bind_tools(tools)

    # 도구 노드 생성
    tool_node = ToolNode(tools)

    def reason_node(state: AgentState) -> dict:
        """
        추론 노드: 현재 상태를 분석하고 다음 행동을 결정합니다.

        - 도구를 호출할지 결정
        - 또는 최종 답변을 생성
        """
        messages = list(state["messages"])
        iteration = state.get("iteration", 0)

        # 첫 메시지가 시스템 메시지가 아니면 추가
        if not messages or not isinstance(messages[0], SystemMessage):
            messages = [SystemMessage(content=REACT_SYSTEM_PROMPT)] + messages

        # 최대 반복 횟수 초과 시 강제 종료
        config = get_config()
        if iteration >= config.agent.max_iterations:
            return {
                "messages": [AIMessage(content="I've reached the maximum number of reasoning steps. Based on the information gathered, here's my best answer: I apologize, but I couldn't complete the full analysis within the allowed steps.")],
                "iteration": iteration + 1,
                "final_answer": "Maximum iterations reached"
            }

        # LLM 호출
        response = llm_with_tools.invoke(messages)

        return {
            "messages": [response],
            "iteration": iteration + 1
        }

    def should_continue(state: AgentState) -> Literal["tools", "end"]:
        """
        다음 노드를 결정하는 조건부 엣지

        - tool_calls가 있으면 → "tools" (도구 실행)
        - 없으면 → "end" (종료)
        """
        messages = state["messages"]
        last_message = messages[-1]

        # 최종 답변이 설정되어 있으면 종료
        if state.get("final_answer"):
            return "end"

        # AIMessage이고 tool_calls가 있으면 도구 실행
        if isinstance(last_message, AIMessage) and last_message.tool_calls:
            return "tools"

        # 그 외에는 종료 (최종 답변)
        return "end"

    def update_tool_results(state: AgentState) -> dict:
        """
        도구 실행 후 결과를 tool_results에 저장합니다.
        (디버깅/로깅용)
        """
        messages = state["messages"]
        tool_results = list(state.get("tool_results", []))

        # 최근 ToolMessage들을 찾아서 저장
        for msg in reversed(messages):
            if isinstance(msg, ToolMessage):
                tool_results.append({
                    "tool_name": msg.name,
                    "tool_input": {},  # 입력은 별도로 추적 필요
                    "result": msg.content[:500],  # 결과 길이 제한
                    "success": True
                })
                break  # 가장 최근 하나만

        return {"tool_results": tool_results}

    # StateGraph 구성
    workflow = StateGraph(AgentState)

    # 노드 추가
    workflow.add_node("reason", reason_node)
    workflow.add_node("tools", tool_node)
    workflow.add_node("update_results", update_tool_results)

    # 엣지 추가
    workflow.set_entry_point("reason")

    # 조건부 엣지: reason → tools 또는 end
    workflow.add_conditional_edges(
        "reason",
        should_continue,
        {
            "tools": "tools",
            "end": END
        }
    )

    # tools → update_results → reason (루프)
    workflow.add_edge("tools", "update_results")
    workflow.add_edge("update_results", "reason")

    # 그래프 컴파일
    return workflow.compile()
