"""
Async Neo4j Driver Module

비동기 Neo4j 드라이버를 통한 Thread Pool 병목 해소.
asyncio.to_thread() 없이 네이티브 async/await 지원.

Features:
- Native async Neo4j driver
- Connection pool 공유
- Async query execution
- Async transaction support
"""

import logging
from typing import Optional, List, Dict, Any
from contextlib import asynccontextmanager

from neo4j import AsyncGraphDatabase, AsyncDriver, AsyncSession, AsyncManagedTransaction
from neo4j.exceptions import ServiceUnavailable, SessionExpired, TransactionError

from .config import get_config

logger = logging.getLogger(__name__)


class AsyncNeo4jDriver:
    """
    Async Neo4j Driver Wrapper

    네이티브 비동기 드라이버를 통해 Thread Pool 병목을 해소합니다.

    Usage:
        driver = AsyncNeo4jDriver()
        await driver.connect()

        # 쿼리 실행
        result = await driver.query("MATCH (n) RETURN n LIMIT 10")

        # 트랜잭션
        async with driver.session() as session:
            async with session.begin_transaction() as tx:
                await tx.run("CREATE (n:Test)")

        await driver.close()
    """

    def __init__(
        self,
        uri: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        max_connection_pool_size: int = 100,
        connection_acquisition_timeout: float = 60.0,
        connection_timeout: float = 30.0,
        max_connection_lifetime: int = 3600,
    ):
        """
        Args:
            uri: Neo4j URI (기본: NEO4J_URI 환경변수)
            username: 사용자명 (기본: NEO4J_USERNAME 환경변수)
            password: 비밀번호 (기본: NEO4J_PASSWORD 환경변수)
            max_connection_pool_size: 최대 커넥션 풀 크기
            connection_acquisition_timeout: 커넥션 획득 대기 시간(초)
            connection_timeout: 커넥션 타임아웃(초)
            max_connection_lifetime: 커넥션 최대 수명(초)
        """
        # Config에서 Neo4j 설정 로드
        config = get_config()
        self._uri = uri or config.neo4j.uri
        self._username = username or config.neo4j.username
        self._password = password or config.neo4j.password

        # 드라이버 설정 (파라미터 우선, 없으면 config 사용)
        self._driver_config = {
            "max_connection_pool_size": max_connection_pool_size if max_connection_pool_size != 100 else config.neo4j.max_pool_size,
            "connection_acquisition_timeout": connection_acquisition_timeout if connection_acquisition_timeout != 60.0 else config.neo4j.connection_acquisition_timeout,
            "connection_timeout": connection_timeout if connection_timeout != 30.0 else config.neo4j.connection_timeout,
            "max_connection_lifetime": max_connection_lifetime if max_connection_lifetime != 3600 else config.neo4j.max_connection_lifetime,
        }

        self._driver: Optional[AsyncDriver] = None
        self._database = config.neo4j.database

    async def connect(self) -> None:
        """드라이버 연결"""
        if self._driver is None:
            self._driver = AsyncGraphDatabase.driver(
                self._uri,
                auth=(self._username, self._password),
                **self._driver_config
            )
            # 연결 확인
            try:
                await self._driver.verify_connectivity()
                logger.info(f"Async Neo4j driver connected to {self._uri}")
            except Exception as e:
                logger.error(f"Failed to connect to Neo4j: {e}")
                raise

    async def close(self) -> None:
        """드라이버 종료"""
        if self._driver is not None:
            await self._driver.close()
            self._driver = None
            logger.info("Async Neo4j driver closed")

    async def ensure_connected(self) -> None:
        """연결 보장 (lazy connection)"""
        if self._driver is None:
            await self.connect()

    @asynccontextmanager
    async def session(self, database: Optional[str] = None):
        """
        Async session context manager

        Usage:
            async with driver.session() as session:
                result = await session.run("MATCH (n) RETURN n")
        """
        await self.ensure_connected()
        session = self._driver.session(database=database or self._database)
        try:
            yield session
        finally:
            await session.close()

    async def query(
        self,
        cypher: str,
        params: Optional[Dict[str, Any]] = None,
        database: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Cypher 쿼리 실행 (비동기)

        Args:
            cypher: Cypher 쿼리문
            params: 쿼리 파라미터
            database: 데이터베이스명 (기본: neo4j)

        Returns:
            쿼리 결과 리스트
        """
        await self.ensure_connected()

        async with self.session(database) as session:
            result = await session.run(cypher, params or {})
            records = await result.data()
            return records

    async def query_single(
        self,
        cypher: str,
        params: Optional[Dict[str, Any]] = None,
        database: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        단일 결과 쿼리 실행 (비동기)

        Args:
            cypher: Cypher 쿼리문
            params: 쿼리 파라미터
            database: 데이터베이스명

        Returns:
            단일 결과 또는 None
        """
        results = await self.query(cypher, params, database)
        return results[0] if results else None

    async def execute_write(
        self,
        cypher: str,
        params: Optional[Dict[str, Any]] = None,
        database: Optional[str] = None
    ) -> None:
        """
        쓰기 쿼리 실행 (비동기, 단일 트랜잭션)

        Args:
            cypher: Cypher 쿼리문 (CREATE, MERGE, SET, DELETE 등)
            params: 쿼리 파라미터
            database: 데이터베이스명
        """
        await self.ensure_connected()

        async def _work(tx: AsyncManagedTransaction) -> None:
            await tx.run(cypher, params or {})

        async with self.session(database) as session:
            await session.execute_write(_work)

    @asynccontextmanager
    async def write_transaction(self, database: Optional[str] = None):
        """
        Write Transaction 컨텍스트 매니저 (명시적 트랜잭션 격리)

        트랜잭션 내 모든 쓰기 작업이 원자적으로 실행됩니다.
        컨텍스트 종료 시 자동 커밋, 예외 발생 시 자동 롤백.

        Usage:
            async with driver.write_transaction() as tx:
                await tx.run("CREATE (n:User {name: $name})", {"name": "Alice"})
                await tx.run("CREATE (n:Log {action: $action})", {"action": "created"})
            # 트랜잭션 자동 커밋

        Args:
            database: 데이터베이스명 (기본: neo4j)

        Yields:
            AsyncManagedTransaction: 트랜잭션 객체
        """
        await self.ensure_connected()

        async with self.session(database) as session:
            tx = await session.begin_transaction()
            try:
                yield tx
                await tx.commit()
                logger.debug("Write transaction committed")
            except Exception as e:
                await tx.rollback()
                logger.error(f"Write transaction rolled back due to: {e}")
                raise

    async def execute_batch_write(
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

        await self.ensure_connected()

        async def _batch_work(tx: AsyncManagedTransaction) -> None:
            for op in operations:
                cypher = op.get("cypher")
                params = op.get("params", {})
                if cypher:
                    await tx.run(cypher, params)

        try:
            async with self.session(database) as session:
                await session.execute_write(_batch_work)
            logger.debug(f"Batch write completed: {len(operations)} operations")
        except Exception as e:
            logger.error(f"Batch write failed: {e}")
            raise TransactionError(f"Batch write failed: {e}") from e

    async def get_schema(self) -> str:
        """
        데이터베이스 스키마 조회 (비동기)

        Returns:
            스키마 문자열
        """
        # Node labels
        labels_result = await self.query("CALL db.labels()")
        labels = [r["label"] for r in labels_result]

        # Relationship types
        rel_result = await self.query("CALL db.relationshipTypes()")
        rel_types = [r["relationshipType"] for r in rel_result]

        # Property keys
        props_result = await self.query("CALL db.propertyKeys()")
        props = [r["propertyKey"] for r in props_result]

        schema_parts = [
            f"Node labels: {', '.join(labels)}",
            f"Relationship types: {', '.join(rel_types)}",
            f"Property keys: {', '.join(props)}"
        ]

        return "\n".join(schema_parts)


# =============================================================================
# 싱글톤 인스턴스
# =============================================================================

_async_driver_instance: Optional[AsyncNeo4jDriver] = None


async def get_async_driver() -> AsyncNeo4jDriver:
    """
    AsyncNeo4jDriver 싱글톤 인스턴스 반환

    Returns:
        AsyncNeo4jDriver 인스턴스
    """
    global _async_driver_instance

    if _async_driver_instance is None:
        _async_driver_instance = AsyncNeo4jDriver()
        await _async_driver_instance.connect()

    return _async_driver_instance


async def close_async_driver() -> None:
    """AsyncNeo4jDriver 종료"""
    global _async_driver_instance

    if _async_driver_instance is not None:
        await _async_driver_instance.close()
        _async_driver_instance = None
