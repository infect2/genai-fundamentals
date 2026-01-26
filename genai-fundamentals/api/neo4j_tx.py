"""
Neo4j Transaction Helper Module

동기 코드에서 Write Transaction 격리를 지원합니다.
LangChain Neo4jGraph의 내부 driver를 활용하여 원자적 트랜잭션을 제공합니다.

Features:
- Write transaction isolation
- Batch write support (atomic multi-statement)
- Automatic rollback on error
- LangChain Neo4jGraph 호환
"""

import logging
from typing import Optional, List, Dict, Any, Callable
from contextlib import contextmanager

from neo4j import ManagedTransaction
from neo4j.exceptions import TransactionError

logger = logging.getLogger(__name__)


class Neo4jTransactionHelper:
    """
    Neo4j 트랜잭션 헬퍼

    LangChain Neo4jGraph 객체의 내부 드라이버를 활용하여
    명시적 write transaction을 제공합니다.

    Usage:
        tx_helper = Neo4jTransactionHelper(graph)

        # 단일 트랜잭션
        with tx_helper.write_transaction() as tx:
            tx.run("CREATE (n:User {name: $name})", {"name": "Alice"})
            tx.run("CREATE (n:Log {action: $action})", {"action": "created"})

        # 배치 쓰기
        tx_helper.execute_batch_write([
            {"cypher": "CREATE (n:User {name: $name})", "params": {"name": "Alice"}},
            {"cypher": "CREATE (n:Log {action: $action})", "params": {"action": "created"}},
        ])
    """

    def __init__(self, graph):
        """
        Args:
            graph: LangChain Neo4jGraph 인스턴스
        """
        self._graph = graph
        self._driver = graph._driver

    @contextmanager
    def write_transaction(self, database: Optional[str] = None):
        """
        Write Transaction 컨텍스트 매니저 (명시적 트랜잭션 격리)

        트랜잭션 내 모든 쓰기 작업이 원자적으로 실행됩니다.
        컨텍스트 종료 시 자동 커밋, 예외 발생 시 자동 롤백.

        Args:
            database: 데이터베이스명 (기본: neo4j)

        Yields:
            Transaction: 트랜잭션 객체
        """
        session = self._driver.session(database=database or "neo4j")
        tx = session.begin_transaction()
        try:
            yield tx
            tx.commit()
            logger.debug("Write transaction committed")
        except Exception as e:
            tx.rollback()
            logger.error(f"Write transaction rolled back due to: {e}")
            raise
        finally:
            session.close()

    def execute_batch_write(
        self,
        operations: List[Dict[str, Any]],
        database: Optional[str] = None
    ) -> None:
        """
        배치 쓰기 실행 (원자적 트랜잭션)

        여러 쓰기 작업을 단일 트랜잭션으로 묶어 원자성을 보장합니다.
        하나라도 실패하면 전체 롤백됩니다.

        Args:
            operations: 쓰기 작업 리스트
                [
                    {"cypher": "CREATE ...", "params": {...}},
                    {"cypher": "MERGE ...", "params": {...}},
                ]
            database: 데이터베이스명

        Raises:
            TransactionError: 트랜잭션 실패 시
        """
        if not operations:
            return

        def _batch_work(tx: ManagedTransaction) -> None:
            for op in operations:
                cypher = op.get("cypher")
                params = op.get("params", {})
                if cypher:
                    tx.run(cypher, params)

        try:
            with self._driver.session(database=database or "neo4j") as session:
                session.execute_write(_batch_work)
            logger.debug(f"Batch write completed: {len(operations)} operations")
        except Exception as e:
            logger.error(f"Batch write failed: {e}")
            raise TransactionError(f"Batch write failed: {e}") from e

    def execute_write(
        self,
        cypher: str,
        params: Optional[Dict[str, Any]] = None,
        database: Optional[str] = None
    ) -> None:
        """
        단일 쓰기 쿼리 실행 (트랜잭션 격리)

        Args:
            cypher: Cypher 쿼리문 (CREATE, MERGE, SET, DELETE 등)
            params: 쿼리 파라미터
            database: 데이터베이스명
        """
        def _work(tx: ManagedTransaction) -> None:
            tx.run(cypher, params or {})

        with self._driver.session(database=database or "neo4j") as session:
            session.execute_write(_work)


# =============================================================================
# 편의 함수
# =============================================================================

def get_tx_helper(graph) -> Neo4jTransactionHelper:
    """
    Neo4jTransactionHelper 인스턴스 반환

    Args:
        graph: LangChain Neo4jGraph 인스턴스

    Returns:
        Neo4jTransactionHelper 인스턴스
    """
    return Neo4jTransactionHelper(graph)


def execute_atomic_writes(
    graph,
    operations: List[Dict[str, Any]],
    database: Optional[str] = None
) -> None:
    """
    원자적 배치 쓰기 실행 (편의 함수)

    Args:
        graph: LangChain Neo4jGraph 인스턴스
        operations: 쓰기 작업 리스트
        database: 데이터베이스명
    """
    helper = Neo4jTransactionHelper(graph)
    helper.execute_batch_write(operations, database)
