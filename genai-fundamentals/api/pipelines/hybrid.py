"""
Hybrid RAG 파이프라인 (Vector + Cypher)

시맨틱 검색과 구조화된 데이터 조회를 결합하여 복합 쿼리를 처리합니다.
"""

from typing import Optional

from ..models import QueryResult
from ..router import RouteDecision
from .utils import extract_intermediate_steps


def execute(
    query_text: str,
    vector_store,
    chain,
    hybrid_chain,
    route_decision: Optional[RouteDecision] = None,
    top_k: int = 3
) -> QueryResult:
    """
    Hybrid RAG 파이프라인 실행

    Args:
        query_text: 사용자 질문
        vector_store: Neo4jVector 인스턴스
        chain: GraphCypherQAChain 인스턴스
        hybrid_chain: Hybrid RAG용 LLM 체인
        route_decision: 라우팅 결정 정보
        top_k: 벡터 검색 문서 수

    Returns:
        QueryResult 객체
    """
    # 1. Vector 검색
    docs = vector_store.similarity_search(query_text, k=top_k)

    vector_context_parts = []
    for i, doc in enumerate(docs, 1):
        title = doc.metadata.get("title", "Unknown")
        plot = doc.page_content
        vector_context_parts.append(f"{i}. {title}: {plot[:200]}...")

    vector_context_str = "\n".join(vector_context_parts)

    # 2. Cypher 쿼리 실행
    cypher_result = chain.invoke({"query": query_text})
    cypher, cypher_context = extract_intermediate_steps(cypher_result)

    cypher_context_str = "\n".join(cypher_context) if cypher_context else "No structured data found."

    # 3. Hybrid 답변 생성
    answer = hybrid_chain.invoke({
        "vector_context": vector_context_str,
        "cypher_context": cypher_context_str,
        "question": query_text
    })

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
