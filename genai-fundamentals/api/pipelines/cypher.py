"""
Cypher RAG 파이프라인 (Text-to-Cypher)

특정 엔티티나 관계를 조회하는 쿼리를 Cypher로 변환하여 실행합니다.
"""

from typing import Optional

from ..models import QueryResult
from ..router import RouteDecision
from .utils import extract_intermediate_steps


def execute(
    query_text: str,
    chain,
    route_decision: Optional[RouteDecision] = None
) -> QueryResult:
    """
    Cypher RAG 파이프라인 실행

    Args:
        query_text: 사용자 질문
        chain: GraphCypherQAChain 인스턴스
        route_decision: 라우팅 결정 정보

    Returns:
        QueryResult 객체
    """
    result = chain.invoke({"query": query_text})
    cypher, context = extract_intermediate_steps(result)

    route_value = route_decision.route.value if route_decision else "cypher"
    route_reasoning = route_decision.reasoning if route_decision else ""

    return QueryResult(
        answer=result["result"],
        cypher=cypher,
        context=context,
        route=route_value,
        route_reasoning=route_reasoning
    )
