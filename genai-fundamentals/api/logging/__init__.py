"""
Elasticsearch Logging Module

REST API의 request/response를 Elasticsearch로 전송하는 로깅 시스템입니다.

Components:
- config.py: Elasticsearch 클라이언트 설정
- schemas.py: 로그 스키마 정의
- middleware.py: FastAPI 미들웨어
"""

from .config import (
    ES_ENABLED,
    ES_HOST,
    ES_PORT,
    ES_INDEX_PREFIX,
    get_es_client,
    get_index_name,
)
from .middleware import ElasticsearchLoggingMiddleware, log_agent_response, log_multi_agent_response
from .schemas import (
    LogEvent,
    HttpInfo,
    RequestInfo,
    ResponseInfo,
    AgentInfo,
    MultiAgentInfo,
    DomainDecisionInfo,
    DomainAgentInfo,
    TokenUsageInfo,
    ClientInfo,
)

__all__ = [
    # Config
    "ES_ENABLED",
    "ES_HOST",
    "ES_PORT",
    "ES_INDEX_PREFIX",
    "get_es_client",
    "get_index_name",
    # Middleware
    "ElasticsearchLoggingMiddleware",
    "log_agent_response",
    "log_multi_agent_response",
    # Schemas
    "LogEvent",
    "HttpInfo",
    "RequestInfo",
    "ResponseInfo",
    "AgentInfo",
    "MultiAgentInfo",
    "DomainDecisionInfo",
    "DomainAgentInfo",
    "TokenUsageInfo",
    "ClientInfo",
]
