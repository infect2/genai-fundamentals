"""
Hybrid RAG 파이프라인 (Vector + Cypher)

시맨틱 검색과 구조화된 데이터 조회를 결합하여 복합 쿼리를 처리합니다.
"""

import os
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from typing import Optional

from ..models import QueryResult
from ..router import RouteDecision
from .utils import extract_intermediate_steps


# 기본 쿼리 타임아웃 (초)
DEFAULT_QUERY_TIMEOUT = float(os.getenv("NEO4J_QUERY_TIMEOUT", "30"))


def execute(
    query_text: str,
    vector_store,
    chain,
    hybrid_chain,
    route_decision: Optional[RouteDecision] = None,
    top_k: int = 3,
    timeout: Optional[float] = None
) -> QueryResult:
    """
    Hybrid RAG 파이프라인 실행 (타임아웃 포함)

    Args:
        query_text: 사용자 질문
        vector_store: Neo4jVector 인스턴스
        chain: GraphCypherQAChain 인스턴스
        hybrid_chain: Hybrid RAG용 LLM 체인
        route_decision: 라우팅 결정 정보
        top_k: 벡터 검색 문서 수
        timeout: 쿼리 타임아웃(초), None이면 기본값 사용

    Returns:
        QueryResult 객체

    Raises:
        TimeoutError: 검색, Cypher 또는 LLM 응답이 타임아웃 시간을 초과한 경우
    """
    effective_timeout = timeout if timeout is not None else DEFAULT_QUERY_TIMEOUT

    # 1. Vector 검색 (타임아웃 적용)
    try:
        with ThreadPoolExecutor(max_workers=1) as executor:
            vector_future = executor.submit(
                vector_store.similarity_search, query_text, k=top_k
            )
            docs = vector_future.result(timeout=effective_timeout)
    except FuturesTimeoutError:
        raise TimeoutError(f"Vector search timed out after {effective_timeout}s")

    vector_context_parts = []
    for i, doc in enumerate(docs, 1):
        title = doc.metadata.get("title", "Unknown")
        plot = doc.page_content
        vector_context_parts.append(f"{i}. {title}: {plot[:200]}...")

    vector_context_str = "\n".join(vector_context_parts)

    # 2. Cypher 쿼리 실행 (타임아웃 적용)
    try:
        with ThreadPoolExecutor(max_workers=1) as executor:
            cypher_future = executor.submit(chain.invoke, {"query": query_text})
            cypher_result = cypher_future.result(timeout=effective_timeout)
    except FuturesTimeoutError:
        raise TimeoutError(f"Cypher query timed out after {effective_timeout}s")

    cypher, cypher_context = extract_intermediate_steps(cypher_result)

    cypher_context_str = "\n".join(cypher_context) if cypher_context else "No structured data found."

    # 3. Hybrid 답변 생성 (타임아웃 적용)
    try:
        with ThreadPoolExecutor(max_workers=1) as executor:
            llm_future = executor.submit(
                hybrid_chain.invoke,
                {
                    "vector_context": vector_context_str,
                    "cypher_context": cypher_context_str,
                    "question": query_text
                }
            )
            answer = llm_future.result(timeout=effective_timeout)
    except FuturesTimeoutError:
        raise TimeoutError(f"LLM generation timed out after {effective_timeout}s")

    # 컨텍스트 통합
    combined_context = [
        f"[Vector] {str(doc.metadata)}" for doc in docs
    ] + [
        f"[Cypher] {c}" for c in cypher_context
    ]

    route_value = route_decision.route.value if route_decision else "hybrid"
    route_reasoning = route_decision.reasoning if route_decision else ""

    return QueryResult(
        answer=answer,
        cypher=cypher,
        context=combined_context,
        route=route_value,
        route_reasoning=route_reasoning
    )
