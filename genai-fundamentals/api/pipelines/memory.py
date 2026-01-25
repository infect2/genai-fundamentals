"""
Memory 파이프라인 (사용자 정보 저장/조회)

사용자가 개인 정보를 저장하거나 조회하려는 요청을 처리합니다.
Neo4j UserMemory 노드에 세션별로 key-value 형태로 저장됩니다.
"""

import json
import logging
from typing import Optional, List

from ..models import QueryResult

logger = logging.getLogger(__name__)
from ..router import RouteDecision
from ..prompts import MEMORY_EXTRACT_TEMPLATE

_USER_MEMORY_NODE_LABEL = "UserMemory"


def store_user_memory(graph, session_id: str, key: str, value: str) -> None:
    """
    사용자 정보를 Neo4j에 저장 (MERGE로 upsert)

    Args:
        graph: Neo4jGraph 인스턴스
        session_id: 세션 식별자
        key: 정보 종류 (예: 차번호, 이메일)
        value: 저장할 값
    """
    graph.query(
        f"""
        MERGE (m:`{_USER_MEMORY_NODE_LABEL}` {{session_id: $session_id, key: $key}})
        SET m.value = $value, m.updated_at = datetime()
        """,
        params={"session_id": session_id, "key": key, "value": value}
    )


def get_user_memory(graph, session_id: str, key: str) -> Optional[str]:
    """
    저장된 사용자 정보 조회

    Args:
        graph: Neo4jGraph 인스턴스
        session_id: 세션 식별자
        key: 정보 종류

    Returns:
        저장된 값 또는 None
    """
    result = graph.query(
        f"""
        MATCH (m:`{_USER_MEMORY_NODE_LABEL}` {{session_id: $session_id, key: $key}})
        RETURN m.value AS value
        """,
        params={"session_id": session_id, "key": key}
    )
    return result[0]["value"] if result else None


def get_all_user_memories(graph, session_id: str) -> List[dict]:
    """
    세션의 모든 저장된 정보 조회

    Args:
        graph: Neo4jGraph 인스턴스
        session_id: 세션 식별자

    Returns:
        [{"key": "...", "value": "..."}, ...] 형태의 리스트
    """
    result = graph.query(
        f"""
        MATCH (m:`{_USER_MEMORY_NODE_LABEL}` {{session_id: $session_id}})
        RETURN m.key AS key, m.value AS value
        ORDER BY m.key
        """,
        params={"session_id": session_id}
    )
    return [{"key": r["key"], "value": r["value"]} for r in result]


def execute(
    query_text: str,
    session_id: str,
    llm,
    graph,
    route_decision: RouteDecision
) -> QueryResult:
    """
    MEMORY 라우트 실행 (사용자 정보 저장/조회)

    LLM으로 사용자 메시지에서 action/key/value를 추출한 후
    store면 Neo4j에 저장, recall이면 조회하여 응답합니다.

    Args:
        query_text: 사용자 메시지
        session_id: 세션 식별자
        llm: ChatOpenAI 인스턴스
        graph: Neo4jGraph 인스턴스
        route_decision: 라우팅 결정 정보

    Returns:
        QueryResult 객체
    """
    extract_result = llm.invoke(
        MEMORY_EXTRACT_TEMPLATE.format(message=query_text)
    )
    # LLM이 markdown 코드블록으로 감싸는 경우 처리
    content = extract_result.content.strip()
    if content.startswith("```"):
        content = content.split("\n", 1)[1]  # 첫 줄(```json) 제거
        content = content.rsplit("```", 1)[0]  # 마지막 ``` 제거

    # Security: JSON 파싱 에러 핸들링
    try:
        parsed = json.loads(content.strip())
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse LLM JSON response: {e}, content: {content[:100]}")
        return QueryResult(
            answer="메모리 요청을 처리할 수 없습니다. 다시 시도해주세요.",
            cypher="",
            context=[],
            route=route_decision.route.value,
            route_reasoning="JSON parse error"
        )

    action = parsed.get("action", "recall")
    key = parsed.get("key", "")
    value = parsed.get("value", "")

    if action == "store" and key and value:
        store_user_memory(graph, session_id, key, value)
        answer = f"'{key}' 정보를 기억했습니다: {value}"
    else:
        stored_value = get_user_memory(graph, session_id, key)
        if stored_value:
            answer = f"{key}은(는) {stored_value}입니다."
        else:
            answer = f"저장된 '{key}' 정보가 없습니다."

    return QueryResult(
        answer=answer,
        cypher="",
        context=[],
        route=route_decision.route.value,
        route_reasoning=route_decision.reasoning
    )
