"""
Agent Registry Module

도메인 에이전트를 등록하고 관리하는 레지스트리입니다.
에이전트 검색, 라우팅, 통계 기능을 제공합니다.

Usage:
    from genai_fundamentals.api.multi_agents.registry import get_registry

    # 에이전트 등록
    registry = get_registry()
    registry.register(TMSAgent(graphrag_service))
    registry.register(WMSAgent(graphrag_service))

    # 도메인으로 에이전트 조회
    tms_agent = registry.get(DomainType.TMS)

    # 모든 에이전트 조회
    all_agents = registry.list_agents()
"""

import logging
from typing import Dict, List, Optional

from .base import BaseDomainAgent, DomainType, DomainRouteDecision

logger = logging.getLogger(__name__)


class AgentRegistry:
    """
    도메인 에이전트 레지스트리

    도메인 에이전트들을 중앙에서 관리하고,
    도메인 기반 조회 및 통계 기능을 제공합니다.
    """

    def __init__(self):
        """레지스트리 초기화"""
        self._agents: Dict[DomainType, BaseDomainAgent] = {}
        self._keywords_cache: Dict[str, DomainType] = {}

    def register(self, agent: BaseDomainAgent) -> None:
        """
        도메인 에이전트 등록

        Args:
            agent: 등록할 도메인 에이전트

        Raises:
            ValueError: 유효하지 않은 에이전트
            RuntimeError: 이미 등록된 도메인
        """
        if not isinstance(agent, BaseDomainAgent):
            raise ValueError(f"Expected BaseDomainAgent, got {type(agent)}")

        if agent.domain == DomainType.UNKNOWN:
            raise ValueError(f"Cannot register agent with UNKNOWN domain: {agent}")

        if agent.domain in self._agents:
            logger.warning(f"Replacing existing agent for domain {agent.domain.value}")

        self._agents[agent.domain] = agent
        logger.info(f"Registered agent: {agent}")

        # 키워드 캐시 업데이트
        for keyword in agent.get_keywords():
            self._keywords_cache[keyword.lower()] = agent.domain

    def unregister(self, domain: DomainType) -> Optional[BaseDomainAgent]:
        """
        도메인 에이전트 등록 해제

        Args:
            domain: 해제할 도메인

        Returns:
            해제된 에이전트 (없으면 None)
        """
        agent = self._agents.pop(domain, None)
        if agent:
            logger.info(f"Unregistered agent: {agent}")
            # 키워드 캐시에서 제거
            keywords_to_remove = [
                k for k, v in self._keywords_cache.items() if v == domain
            ]
            for k in keywords_to_remove:
                del self._keywords_cache[k]
        return agent

    def get(self, domain: DomainType) -> Optional[BaseDomainAgent]:
        """
        도메인으로 에이전트 조회

        Args:
            domain: 조회할 도메인

        Returns:
            해당 도메인의 에이전트 (없으면 None)
        """
        return self._agents.get(domain)

    def get_by_name(self, domain_name: str) -> Optional[BaseDomainAgent]:
        """
        도메인 이름으로 에이전트 조회

        Args:
            domain_name: 도메인 이름 문자열 (e.g., "tms", "wms")

        Returns:
            해당 도메인의 에이전트 (없으면 None)
        """
        domain = DomainType.from_string(domain_name)
        return self.get(domain)

    def list_agents(self) -> List[BaseDomainAgent]:
        """
        등록된 모든 에이전트 목록 반환

        Returns:
            에이전트 리스트
        """
        return list(self._agents.values())

    def list_domains(self) -> List[DomainType]:
        """
        등록된 모든 도메인 목록 반환

        Returns:
            도메인 리스트
        """
        return list(self._agents.keys())

    def has_domain(self, domain: DomainType) -> bool:
        """
        해당 도메인이 등록되어 있는지 확인

        Args:
            domain: 확인할 도메인

        Returns:
            등록 여부
        """
        return domain in self._agents

    def get_agent_info(self) -> List[dict]:
        """
        등록된 에이전트 정보 목록 반환 (API용)

        Returns:
            에이전트 정보 딕셔너리 리스트
        """
        return [
            {
                "domain": agent.domain.value,
                "description": agent.description,
                "tools_count": len(agent.get_tools()),
                "keywords": agent.get_keywords()
            }
            for agent in self._agents.values()
        ]

    def route_by_keywords(self, query: str) -> Optional[DomainType]:
        """
        키워드 기반 간단한 도메인 라우팅

        Args:
            query: 사용자 쿼리

        Returns:
            매칭된 도메인 (없으면 None)
        """
        query_lower = query.lower()
        for keyword, domain in self._keywords_cache.items():
            if keyword in query_lower:
                return domain
        return None

    def get_schema_all(self) -> str:
        """
        모든 도메인의 스키마를 통합하여 반환

        Returns:
            통합 스키마 문자열
        """
        schemas = []
        for agent in self._agents.values():
            schema = agent.get_schema_subset()
            if schema:
                schemas.append(f"## {agent.domain.value.upper()} Domain\n{schema}")
        return "\n\n".join(schemas)

    def __len__(self) -> int:
        return len(self._agents)

    def __contains__(self, domain: DomainType) -> bool:
        return domain in self._agents

    def __repr__(self) -> str:
        domains = ", ".join(d.value for d in self._agents.keys())
        return f"AgentRegistry([{domains}])"


# =============================================================================
# 싱글톤 인스턴스
# =============================================================================

_registry_instance: Optional[AgentRegistry] = None


def get_registry() -> AgentRegistry:
    """
    AgentRegistry 싱글톤 인스턴스 반환

    Returns:
        AgentRegistry 인스턴스
    """
    global _registry_instance
    if _registry_instance is None:
        _registry_instance = AgentRegistry()
    return _registry_instance


def reset_registry() -> None:
    """
    레지스트리 리셋 (테스트용)
    """
    global _registry_instance
    _registry_instance = None
