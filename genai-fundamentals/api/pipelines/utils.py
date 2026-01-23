"""
파이프라인 공통 유틸리티
"""

from typing import List


def extract_intermediate_steps(result: dict) -> tuple[str, List[str]]:
    """
    Chain 실행 결과에서 Cypher 쿼리와 컨텍스트 추출

    Args:
        result: chain.invoke() 반환값

    Returns:
        (cypher_query, context_list) 튜플
    """
    cypher = ""
    context = []

    if "intermediate_steps" in result:
        for step in result["intermediate_steps"]:
            if isinstance(step, dict):
                if "query" in step:
                    cypher = step["query"]
                if "context" in step:
                    ctx = step["context"]
                    context = ctx if isinstance(ctx, list) else [ctx]

    return cypher, [str(c) for c in context]
