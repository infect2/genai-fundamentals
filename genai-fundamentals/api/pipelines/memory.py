"""
Memory 파이프라인 (사용자 정보 저장/조회)

사용자가 개인 정보를 저장하거나 조회하려는 요청을 처리합니다.
Neo4j UserMemory 노드에 세션별로 key-value 형태로 저장됩니다.
"""

import json
import logging
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from typing import Optional, List

from ..models import QueryResult
from ..router import RouteDecision
from ..prompts import MEMORY_EXTRACT_TEMPLATE
from ..neo4j_tx import Neo4jTransactionHelper
from ..config import get_config

logger = logging.getLogger(__name__)

_USER_MEMORY_NODE_LABEL = "UserMemory"


def store_user_memory(
    graph,
    session_id: str,
    key: str,
    value: str,
    timeout: Optional[float] = None
) -> None:
    """
    사용자 정보를 Neo4j에 저장 (트랜잭션 격리, 타임아웃 적용)

    Write Transaction을 사용하여 데이터 일관성을 보장합니다.
    MERGE + SET이 원자적으로 실행되며, 실패 시 자동 롤백됩니다.

    Args:
        graph: Neo4jGraph 인스턴스
        session_id: 세션 식별자
        key: 정보 종류 (예: 차번호, 이메일)
        value: 저장할 값
        timeout: 쿼리 타임아웃(초)

    Raises:
        TimeoutError: 저장이 타임아웃 시간을 초과한 경우
    """
    effective_timeout = timeout if timeout is not None else get_config().neo4j.query_timeout

    def _store():
        tx_helper = Neo4jTransactionHelper(graph)
        tx_helper.execute_write(
            f"""
            MERGE (m:`{_USER_MEMORY_NODE_LABEL}` {{session_id: $session_id, key: $key}})
            SET m.value = $value, m.updated_at = datetime()
            """,
            params={"session_id": session_id, "key": key, "value": value}
        )

    try:
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(_store)
            future.result(timeout=effective_timeout)
    except FuturesTimeoutError:
        raise TimeoutError(f"Memory store timed out after {effective_timeout}s")


def get_user_memory(
    graph,
    session_id: str,
    key: str,
    timeout: Optional[float] = None
) -> Optional[str]:
    """
    저장된 사용자 정보 조회 (타임아웃 적용)

    Args:
        graph: Neo4jGraph 인스턴스
        session_id: 세션 식별자
        key: 정보 종류
        timeout: 쿼리 타임아웃(초)

    Returns:
        저장된 값 또는 None

    Raises:
        TimeoutError: 조회가 타임아웃 시간을 초과한 경우
    """
    effective_timeout = timeout if timeout is not None else get_config().neo4j.query_timeout

    def _get():
        return graph.query(
            f"""
            MATCH (m:`{_USER_MEMORY_NODE_LABEL}` {{session_id: $session_id, key: $key}})
            RETURN m.value AS value
            """,
            params={"session_id": session_id, "key": key}
        )

    try:
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(_get)
            result = future.result(timeout=effective_timeout)
    except FuturesTimeoutError:
        raise TimeoutError(f"Memory get timed out after {effective_timeout}s")

    return result[0]["value"] if result else None


def get_all_user_memories(
    graph,
    session_id: str,
    timeout: Optional[float] = None
) -> List[dict]:
    """
    세션의 모든 저장된 정보 조회 (타임아웃 적용)

    Args:
        graph: Neo4jGraph 인스턴스
        session_id: 세션 식별자
        timeout: 쿼리 타임아웃(초)

    Returns:
        [{"key": "...", "value": "..."}, ...] 형태의 리스트

    Raises:
        TimeoutError: 조회가 타임아웃 시간을 초과한 경우
    """
    effective_timeout = timeout if timeout is not None else get_config().neo4j.query_timeout

    def _get_all():
        return graph.query(
            f"""
            MATCH (m:`{_USER_MEMORY_NODE_LABEL}` {{session_id: $session_id}})
            RETURN m.key AS key, m.value AS value
            ORDER BY m.key
            """,
            params={"session_id": session_id}
        )

    try:
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(_get_all)
            result = future.result(timeout=effective_timeout)
    except FuturesTimeoutError:
        raise TimeoutError(f"Memory get all timed out after {effective_timeout}s")

    return [{"key": r["key"], "value": r["value"]} for r in result]


def execute(
    query_text: str,
    session_id: str,
    llm,
    graph,
    route_decision: RouteDecision,
    timeout: Optional[float] = None
) -> QueryResult:
    """
    MEMORY 라우트 실행 (사용자 정보 저장/조회, 타임아웃 적용)

    LLM으로 사용자 메시지에서 action/key/value를 추출한 후
    store면 Neo4j에 저장, recall이면 조회하여 응답합니다.

    Args:
        query_text: 사용자 메시지
        session_id: 세션 식별자
        llm: ChatOpenAI 인스턴스
        graph: Neo4jGraph 인스턴스
        route_decision: 라우팅 결정 정보
        timeout: 쿼리 타임아웃(초), None이면 기본값 사용

    Returns:
        QueryResult 객체

    Raises:
        TimeoutError: LLM 또는 DB 작업이 타임아웃 시간을 초과한 경우
    """
    effective_timeout = timeout if timeout is not None else get_config().neo4j.query_timeout

    # LLM으로 메모리 액션 추출 (타임아웃 적용)
    try:
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(
                llm.invoke,
                MEMORY_EXTRACT_TEMPLATE.format(message=query_text)
            )
            extract_result = future.result(timeout=effective_timeout)
    except FuturesTimeoutError:
        raise TimeoutError(f"Memory extraction timed out after {effective_timeout}s")

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
        store_user_memory(graph, session_id, key, value, timeout=effective_timeout)
        answer = f"'{key}' 정보를 기억했습니다: {value}"
    else:
        stored_value = get_user_memory(graph, session_id, key, timeout=effective_timeout)
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
