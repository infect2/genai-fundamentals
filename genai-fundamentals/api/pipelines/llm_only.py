"""
LLM Only 파이프라인

DB 조회 없이 LLM이 직접 응답하는 일반 질문을 처리합니다.
"""

from typing import Optional

from ..models import QueryResult
from ..router import RouteDecision


def execute(
    query_text: str,
    llm_only_chain,
    route_decision: Optional[RouteDecision] = None
) -> QueryResult:
    """
    LLM Only 파이프라인 실행

    Args:
        query_text: 사용자 질문
        llm_only_chain: LLM Only용 체인
        route_decision: 라우팅 결정 정보

    Returns:
        QueryResult 객체
    """
    answer = llm_only_chain.invoke({"question": query_text})

    route_value = route_decision.route.value if route_decision else "llm_only"
    route_reasoning = route_decision.reasoning if route_decision else ""

    return QueryResult(
        answer=answer,
        cypher="",
        context=[],
        route=route_value,
        route_reasoning=route_reasoning
    )
