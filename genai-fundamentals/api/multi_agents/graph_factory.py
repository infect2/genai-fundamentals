"""
Domain Agent Graph Factory Module

도메인 에이전트용 LangGraph StateGraph를 생성하는 팩토리입니다.
기존 AgentService의 그래프 패턴을 재사용하되,
도메인별 도구와 프롬프트를 주입할 수 있도록 확장합니다.

Usage:
    from genai_fundamentals.api.multi_agents.graph_factory import create_domain_agent_graph

    graph = create_domain_agent_graph(
        domain_agent=tms_agent,
        graphrag_service=service,
        model_name="gpt-4o"
    )
    result = graph.invoke(initial_state)
"""

import logging
from typing import Optional, Sequence

from langchain_core.messages import BaseMessage, SystemMessage, AIMessage
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode

from ..agent.state import AgentState, ToolResult
from ..config import get_config

logger = logging.getLogger(__name__)


def create_domain_agent_graph(
    domain_agent,
    graphrag_service,
    model_name: Optional[str] = None
):
    """
    도메인 에이전트용 LangGraph StateGraph 생성

    기존 AgentService의 ReAct 패턴을 재사용하면서,
    도메인별 도구와 시스템 프롬프트를 적용합니다.

    Args:
        domain_agent: BaseDomainAgent 인스턴스
        graphrag_service: GraphRAGService 인스턴스
        model_name: 사용할 LLM 모델명

    Returns:
        CompiledGraph 인스턴스
    """
    from ...tools.llm_provider import create_langchain_llm

    config = get_config()

    # LLM 생성
    llm = create_langchain_llm(model_name=model_name, temperature=0)

    # 도메인 전용 도구 가져오기
    tools = domain_agent.get_tools()

    # 도구가 있으면 LLM에 바인딩
    if tools:
        llm_with_tools = llm.bind_tools(tools)
    else:
        llm_with_tools = llm

    # 도메인 시스템 프롬프트 가져오기
    system_prompt = domain_agent.get_system_prompt()

    # 스키마 정보 추가
    schema_info = domain_agent.get_schema_subset()
    if schema_info:
        system_prompt += f"\n\n[Domain Schema]\n{schema_info}"

    # 노드 함수 정의
    def reason(state: AgentState) -> dict:
        """LLM reasoning 노드"""
        messages = list(state["messages"])

        # 시스템 프롬프트 주입 (첫 번째 메시지가 시스템 메시지가 아닌 경우)
        if not messages or not isinstance(messages[0], SystemMessage):
            messages.insert(0, SystemMessage(content=system_prompt))

        response = llm_with_tools.invoke(messages)
        return {"messages": [response]}

    def update_results(state: AgentState) -> dict:
        """도구 실행 결과 업데이트 노드"""
        messages = state["messages"]
        tool_results = list(state.get("tool_results", []))
        iteration = state.get("iteration", 0)

        # 마지막 도구 결과 추출
        for msg in reversed(messages):
            if hasattr(msg, "name") and hasattr(msg, "content"):
                tool_results.append(ToolResult(
                    tool_name=msg.name,
                    tool_input={},  # ToolMessage에서는 input을 알 수 없음
                    result=msg.content[:500] if len(msg.content) > 500 else msg.content,
                    success=True
                ))
                break

        return {
            "tool_results": tool_results,
            "iteration": iteration + 1
        }

    def should_continue(state: AgentState) -> str:
        """
        다음 노드 결정 (조건부 엣지)

        - 최대 반복 횟수 초과 시 종료
        - 도구 호출이 있으면 tools 노드로
        - 그렇지 않으면 종료
        """
        messages = state["messages"]
        iteration = state.get("iteration", 0)
        max_iterations = config.agent.max_iterations

        # 최대 반복 횟수 체크
        if iteration >= max_iterations:
            logger.warning(f"Max iterations ({max_iterations}) reached for domain {domain_agent.domain.value}")
            return END

        # 마지막 메시지 확인
        if messages:
            last_message = messages[-1]
            if isinstance(last_message, AIMessage):
                if last_message.tool_calls:
                    return "tools"

        return END

    # StateGraph 생성
    workflow = StateGraph(AgentState)

    # 노드 추가
    workflow.add_node("reason", reason)
    if tools:
        workflow.add_node("tools", ToolNode(tools))
        workflow.add_node("update_results", update_results)

    # 엣지 추가
    workflow.set_entry_point("reason")

    if tools:
        workflow.add_conditional_edges(
            "reason",
            should_continue,
            {
                "tools": "tools",
                END: END
            }
        )
        workflow.add_edge("tools", "update_results")
        workflow.add_edge("update_results", "reason")
    else:
        workflow.add_edge("reason", END)

    return workflow.compile()
