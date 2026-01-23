"""
Vector RAG 파이프라인 (시맨틱 검색)

줄거리, 분위기, 테마 기반으로 유사한 영화를 검색합니다.
"""

from typing import Optional

from ..models import QueryResult
from ..router import RouteDecision


def execute(
    query_text: str,
    vector_store,
    vector_chain,
    route_decision: Optional[RouteDecision] = None,
    top_k: int = 5
) -> QueryResult:
    """
    Vector RAG 파이프라인 실행

    Args:
        query_text: 사용자 질문
        vector_store: Neo4jVector 인스턴스
        vector_chain: Vector RAG용 LLM 체인
        route_decision: 라우팅 결정 정보
        top_k: 검색할 문서 수

    Returns:
        QueryResult 객체
    """
    # Vector Store에서 유사 문서 검색
    docs = vector_store.similarity_search(query_text, k=top_k)

    # 컨텍스트 구성
    context_parts = []
    for i, doc in enumerate(docs, 1):
        title = doc.metadata.get("title", "Unknown")
        plot = doc.page_content
        context_parts.append(f"{i}. {title}: {plot[:200]}...")

    context_str = "\n".join(context_parts)

    # LLM으로 답변 생성
    answer = vector_chain.invoke({
        "context": context_str,
        "question": query_text
    })

    route_value = route_decision.route.value if route_decision else "vector"
    route_reasoning = route_decision.reasoning if route_decision else ""

    return QueryResult(
        answer=answer,
        cypher="",
        context=[str(doc.metadata) for doc in docs],
        route=route_value,
        route_reasoning=route_reasoning
    )
