"""
Vector RAG 파이프라인 (시맨틱 검색)

내용, 설명, 테마 기반으로 유사한 엔티티를 검색합니다.
"""

import os
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from typing import Optional

from ..models import QueryResult
from ..router import RouteDecision


# 기본 쿼리 타임아웃 (초)
DEFAULT_QUERY_TIMEOUT = float(os.getenv("NEO4J_QUERY_TIMEOUT", "30"))


def execute(
    query_text: str,
    vector_store,
    vector_chain,
    route_decision: Optional[RouteDecision] = None,
    top_k: int = 5,
    timeout: Optional[float] = None
) -> QueryResult:
    """
    Vector RAG 파이프라인 실행 (타임아웃 포함)

    Args:
        query_text: 사용자 질문
        vector_store: Neo4jVector 인스턴스
        vector_chain: Vector RAG용 LLM 체인
        route_decision: 라우팅 결정 정보
        top_k: 검색할 문서 수
        timeout: 쿼리 타임아웃(초), None이면 기본값 사용

    Returns:
        QueryResult 객체

    Raises:
        TimeoutError: 검색 또는 LLM 응답이 타임아웃 시간을 초과한 경우
    """
    effective_timeout = timeout if timeout is not None else DEFAULT_QUERY_TIMEOUT

    # Vector Store에서 유사 문서 검색 (타임아웃 적용)
    try:
        with ThreadPoolExecutor(max_workers=1) as executor:
            search_future = executor.submit(
                vector_store.similarity_search, query_text, k=top_k
            )
            docs = search_future.result(timeout=effective_timeout)
    except FuturesTimeoutError:
        raise TimeoutError(f"Vector search timed out after {effective_timeout}s")

    # 컨텍스트 구성
    context_parts = []
    for i, doc in enumerate(docs, 1):
        title = doc.metadata.get("title", "Unknown")
        plot = doc.page_content
        context_parts.append(f"{i}. {title}: {plot[:200]}...")

    context_str = "\n".join(context_parts)

    # LLM으로 답변 생성 (타임아웃 적용)
    try:
        with ThreadPoolExecutor(max_workers=1) as executor:
            llm_future = executor.submit(
                vector_chain.invoke,
                {"context": context_str, "question": query_text}
            )
            answer = llm_future.result(timeout=effective_timeout)
    except FuturesTimeoutError:
        raise TimeoutError(f"LLM generation timed out after {effective_timeout}s")

    route_value = route_decision.route.value if route_decision else "vector"
    route_reasoning = route_decision.reasoning if route_decision else ""

    return QueryResult(
        answer=answer,
        cypher="",
        context=[str(doc.metadata) for doc in docs],
        route=route_value,
        route_reasoning=route_reasoning
    )
