"""
Cypher RAG 파이프라인 (Text-to-Cypher)

특정 엔티티나 관계를 조회하는 쿼리를 Cypher로 변환하여 실행합니다.
"""

from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from typing import Optional

from ..models import QueryResult
from ..router import RouteDecision
from ..config import get_config
from .utils import extract_intermediate_steps


def execute(
    query_text: str,
    chain,
    route_decision: Optional[RouteDecision] = None,
    timeout: Optional[float] = None
) -> QueryResult:
    """
    Cypher RAG 파이프라인 실행 (타임아웃 포함)

    Args:
        query_text: 사용자 질문
        chain: GraphCypherQAChain 인스턴스
        route_decision: 라우팅 결정 정보
        timeout: 쿼리 타임아웃(초), None이면 기본값 사용

    Returns:
        QueryResult 객체

    Raises:
        TimeoutError: 쿼리가 타임아웃 시간을 초과한 경우
    """
    effective_timeout = timeout if timeout is not None else get_config().neo4j.query_timeout

    try:
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(chain.invoke, {"query": query_text})
            result = future.result(timeout=effective_timeout)
    except FuturesTimeoutError:
        raise TimeoutError(f"Cypher query timed out after {effective_timeout}s")

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
