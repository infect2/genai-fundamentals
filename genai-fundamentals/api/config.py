"""
Central Configuration Module

모든 설정을 중앙에서 관리합니다.
환경변수에서 읽어오며, 기본값을 제공합니다.

Usage:
    from .config import get_config

    config = get_config()
    print(config.agent.max_iterations)
    print(config.neo4j.max_pool_size)
"""

import os
from dataclasses import dataclass, field
from typing import Optional
from functools import lru_cache


@dataclass(frozen=True)
class AgentConfig:
    """ReAct Agent 설정"""

    # 최대 반복 횟수 (무한 루프 방지)
    max_iterations: int = field(default_factory=lambda: int(os.getenv("AGENT_MAX_ITERATIONS", "10")))

    # Agent 쿼리 타임아웃 (초)
    query_timeout: float = field(default_factory=lambda: float(os.getenv("AGENT_QUERY_TIMEOUT", "120")))

    # 도구 결과 최대 길이 (문자)
    tool_result_max_length: int = field(default_factory=lambda: int(os.getenv("AGENT_TOOL_RESULT_MAX_LENGTH", "500")))


@dataclass(frozen=True)
class Neo4jConfig:
    """Neo4j 연결 설정"""

    # 연결 정보
    uri: str = field(default_factory=lambda: os.getenv("NEO4J_URI", ""))
    username: str = field(default_factory=lambda: os.getenv("NEO4J_USERNAME", "neo4j"))
    password: str = field(default_factory=lambda: os.getenv("NEO4J_PASSWORD", ""))
    database: str = field(default_factory=lambda: os.getenv("NEO4J_DATABASE", "neo4j"))

    # 커넥션 풀 설정
    max_pool_size: int = field(default_factory=lambda: int(os.getenv("NEO4J_MAX_POOL_SIZE", "100")))
    connection_acquisition_timeout: float = field(default_factory=lambda: float(os.getenv("NEO4J_CONNECTION_ACQUISITION_TIMEOUT", "60")))
    connection_timeout: float = field(default_factory=lambda: float(os.getenv("NEO4J_CONNECTION_TIMEOUT", "30")))
    max_connection_lifetime: int = field(default_factory=lambda: int(os.getenv("NEO4J_MAX_CONNECTION_LIFETIME", "3600")))

    # 쿼리 타임아웃
    query_timeout: float = field(default_factory=lambda: float(os.getenv("NEO4J_QUERY_TIMEOUT", "30")))

    @property
    def driver_config(self) -> dict:
        """Neo4j 드라이버 설정 딕셔너리 반환"""
        return {
            "max_connection_pool_size": self.max_pool_size,
            "connection_acquisition_timeout": self.connection_acquisition_timeout,
            "connection_timeout": self.connection_timeout,
            "max_connection_lifetime": self.max_connection_lifetime,
        }


@dataclass(frozen=True)
class CacheConfig:
    """캐시 설정"""

    # Query Cache
    query_cache_enabled: bool = field(default_factory=lambda: os.getenv("QUERY_CACHE_ENABLED", "true").lower() == "true")
    query_cache_max_size: int = field(default_factory=lambda: int(os.getenv("QUERY_CACHE_MAX_SIZE", "1000")))
    query_cache_ttl: float = field(default_factory=lambda: float(os.getenv("QUERY_CACHE_TTL", "300")))  # 5분
    schema_cache_ttl: float = field(default_factory=lambda: float(os.getenv("SCHEMA_CACHE_TTL", "3600")))  # 1시간

    # History Cache
    history_cache_ttl: float = field(default_factory=lambda: float(os.getenv("HISTORY_CACHE_TTL", "1800")))  # 30분
    history_cache_max_sessions: int = field(default_factory=lambda: int(os.getenv("HISTORY_CACHE_MAX_SESSIONS", "500")))
    history_cache_max_messages: int = field(default_factory=lambda: int(os.getenv("HISTORY_CACHE_MAX_MESSAGES", "100")))


@dataclass(frozen=True)
class ConcurrencyConfig:
    """동시성 제어 설정"""

    # LLM Semaphore
    max_concurrent_llm: int = field(default_factory=lambda: int(os.getenv("MAX_CONCURRENT_LLM", "10")))

    # Request Coalescing
    coalescing_enabled: bool = field(default_factory=lambda: os.getenv("COALESCING_ENABLED", "true").lower() == "true")


@dataclass(frozen=True)
class LoggingConfig:
    """로깅 설정"""

    # Elasticsearch
    es_enabled: bool = field(default_factory=lambda: os.getenv("ES_LOGGING_ENABLED", "false").lower() == "true")
    es_host: str = field(default_factory=lambda: os.getenv("ES_HOST", "localhost"))
    es_port: int = field(default_factory=lambda: int(os.getenv("ES_PORT", "9200")))
    es_index_prefix: str = field(default_factory=lambda: os.getenv("ES_INDEX_PREFIX", "graphrag-logs"))
    es_api_key: str = field(default_factory=lambda: os.getenv("ES_API_KEY", ""))


@dataclass(frozen=True)
class AppConfig:
    """전체 애플리케이션 설정"""

    agent: AgentConfig = field(default_factory=AgentConfig)
    neo4j: Neo4jConfig = field(default_factory=Neo4jConfig)
    cache: CacheConfig = field(default_factory=CacheConfig)
    concurrency: ConcurrencyConfig = field(default_factory=ConcurrencyConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)


# =============================================================================
# 싱글톤 인스턴스
# =============================================================================

_config_instance: Optional[AppConfig] = None


def get_config() -> AppConfig:
    """
    AppConfig 싱글톤 인스턴스 반환

    Returns:
        AppConfig 인스턴스
    """
    global _config_instance
    if _config_instance is None:
        _config_instance = AppConfig()
    return _config_instance


def reset_config() -> None:
    """
    설정 인스턴스 리셋 (테스트용)
    """
    global _config_instance
    _config_instance = None


# =============================================================================
# 편의 함수
# =============================================================================

def get_neo4j_driver_config() -> dict:
    """Neo4j 드라이버 설정 딕셔너리 반환 (편의 함수)"""
    return get_config().neo4j.driver_config
