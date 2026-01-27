"""
Multi-Agent System Module

연합형 멀티 에이전트 시스템의 핵심 모듈입니다.
WMS, TMS, FMS, TAP! 도메인 에이전트와 Master Orchestrator를 제공합니다.

Usage:
    from genai_fundamentals.api.multi_agents import (
        BaseDomainAgent,
        DomainType,
        DomainRouteDecision,
        AgentRegistry,
        get_registry
    )

    # 에이전트 등록
    registry = get_registry()
    registry.register(TMSAgent())

    # 도메인 라우팅
    decision = registry.route_query("배송 현황 알려줘")
    print(decision.domain)  # DomainType.TMS
"""

from .base import (
    DomainType,
    DomainRouteDecision,
    BaseDomainAgent,
    DomainAgentResult,
)
from .registry import AgentRegistry, get_registry

__all__ = [
    # Base
    "DomainType",
    "DomainRouteDecision",
    "BaseDomainAgent",
    "DomainAgentResult",
    # Registry
    "AgentRegistry",
    "get_registry",
]
