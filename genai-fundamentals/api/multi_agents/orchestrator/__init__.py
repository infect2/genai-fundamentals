"""
Master Orchestrator Module

멀티 에이전트 시스템의 Master Orchestrator를 정의합니다.
사용자 쿼리를 분석하여 적절한 도메인 에이전트로 라우팅하고,
크로스 도메인 처리를 조율합니다.

Usage:
    from genai_fundamentals.api.multi_agents.orchestrator import (
        OrchestratorService,
        DomainRouter,
        get_orchestrator,
    )

    orchestrator = get_orchestrator(registry, graphrag_service)
    result = await orchestrator.query_async("배송 현황 알려줘")
"""

from .router import DomainRouter
from .state import OrchestratorState
from .service import OrchestratorService, MultiAgentResult, get_orchestrator, reset_orchestrator

__all__ = [
    "DomainRouter",
    "OrchestratorState",
    "OrchestratorService",
    "MultiAgentResult",
    "get_orchestrator",
    "reset_orchestrator",
]
