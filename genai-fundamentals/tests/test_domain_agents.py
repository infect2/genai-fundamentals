"""
Domain Agents Tests

도메인 에이전트의 기본 기능을 테스트합니다.

실행 방법:
    pytest genai-fundamentals/tests/test_domain_agents.py -v
"""

import sys
import os
import importlib

# 프로젝트 루트를 sys.path에 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pytest
from unittest.mock import Mock, MagicMock

# hyphenated 패키지명은 importlib으로 로드
_base_mod = importlib.import_module("genai-fundamentals.api.multi_agents.base")
_registry_mod = importlib.import_module("genai-fundamentals.api.multi_agents.registry")
_tms_mod = importlib.import_module("genai-fundamentals.api.multi_agents.tms")
_wms_mod = importlib.import_module("genai-fundamentals.api.multi_agents.wms")
_fms_mod = importlib.import_module("genai-fundamentals.api.multi_agents.fms")
_tap_mod = importlib.import_module("genai-fundamentals.api.multi_agents.tap")

BaseDomainAgent = _base_mod.BaseDomainAgent
DomainType = _base_mod.DomainType
DomainAgentResult = _base_mod.DomainAgentResult
AgentRegistry = _registry_mod.AgentRegistry
get_registry = _registry_mod.get_registry
reset_registry = _registry_mod.reset_registry
TMSAgent = _tms_mod.TMSAgent
WMSAgent = _wms_mod.WMSAgent
FMSAgent = _fms_mod.FMSAgent
TAPAgent = _tap_mod.TAPAgent


class TestAgentRegistry:
    """에이전트 레지스트리 테스트"""

    def setup_method(self):
        """테스트 전 레지스트리 초기화"""
        reset_registry()
        self.registry = get_registry()
        self.mock_service = Mock()

    def teardown_method(self):
        """테스트 후 레지스트리 정리"""
        reset_registry()

    def test_register_agent(self):
        """에이전트 등록"""
        tms_agent = TMSAgent(graphrag_service=self.mock_service)
        self.registry.register(tms_agent)

        assert self.registry.has_domain(DomainType.TMS)
        assert len(self.registry) == 1

    def test_get_agent(self):
        """에이전트 조회"""
        tms_agent = TMSAgent(graphrag_service=self.mock_service)
        self.registry.register(tms_agent)

        retrieved = self.registry.get(DomainType.TMS)
        assert retrieved is not None
        assert retrieved.domain == DomainType.TMS

    def test_get_by_name(self):
        """이름으로 에이전트 조회"""
        tms_agent = TMSAgent(graphrag_service=self.mock_service)
        self.registry.register(tms_agent)

        retrieved = self.registry.get_by_name("tms")
        assert retrieved is not None
        assert retrieved.domain == DomainType.TMS

    def test_list_agents(self):
        """에이전트 목록 조회"""
        tms_agent = TMSAgent(graphrag_service=self.mock_service)
        wms_agent = WMSAgent(graphrag_service=self.mock_service)

        self.registry.register(tms_agent)
        self.registry.register(wms_agent)

        agents = self.registry.list_agents()
        assert len(agents) == 2

    def test_unregister_agent(self):
        """에이전트 등록 해제"""
        tms_agent = TMSAgent(graphrag_service=self.mock_service)
        self.registry.register(tms_agent)

        unregistered = self.registry.unregister(DomainType.TMS)
        assert unregistered is not None
        assert not self.registry.has_domain(DomainType.TMS)

    def test_get_agent_info(self):
        """에이전트 정보 조회"""
        tms_agent = TMSAgent(graphrag_service=self.mock_service)
        self.registry.register(tms_agent)

        info = self.registry.get_agent_info()
        assert len(info) == 1
        assert info[0]["domain"] == "tms"
        assert "description" in info[0]


class TestTMSAgent:
    """TMS 에이전트 테스트"""

    def setup_method(self):
        self.mock_service = Mock()
        self.agent = TMSAgent(graphrag_service=self.mock_service)

    def test_domain(self):
        """도메인 타입 확인"""
        assert self.agent.domain == DomainType.TMS

    def test_description(self):
        """설명 확인"""
        assert "운송" in self.agent.description

    def test_keywords(self):
        """키워드 확인"""
        keywords = self.agent.get_keywords()
        assert "배송" in keywords
        assert "운송" in keywords

    def test_system_prompt(self):
        """시스템 프롬프트 확인"""
        prompt = self.agent.get_system_prompt()
        assert "TMS" in prompt

    def test_schema_subset(self):
        """스키마 확인"""
        schema = self.agent.get_schema_subset()
        assert "Shipment" in schema
        assert "Carrier" in schema

    def test_get_tools(self):
        """도구 생성 확인"""
        tools = self.agent.get_tools()
        assert len(tools) > 0
        tool_names = [t.name for t in tools]
        assert "tms_shipment_status" in tool_names

    def test_is_relevant_query(self):
        """관련 쿼리 판별"""
        assert TMSAgent.is_relevant_query("배송 현황")
        assert TMSAgent.is_relevant_query("shipment status")
        assert not TMSAgent.is_relevant_query("안녕하세요")


class TestWMSAgent:
    """WMS 에이전트 테스트"""

    def setup_method(self):
        self.mock_service = Mock()
        self.agent = WMSAgent(graphrag_service=self.mock_service)

    def test_domain(self):
        assert self.agent.domain == DomainType.WMS

    def test_keywords(self):
        keywords = self.agent.get_keywords()
        assert "창고" in keywords
        assert "재고" in keywords

    def test_get_tools(self):
        tools = self.agent.get_tools()
        tool_names = [t.name for t in tools]
        assert "wms_inventory_query" in tool_names


class TestFMSAgent:
    """FMS 에이전트 테스트"""

    def setup_method(self):
        self.mock_service = Mock()
        self.agent = FMSAgent(graphrag_service=self.mock_service)

    def test_domain(self):
        assert self.agent.domain == DomainType.FMS

    def test_keywords(self):
        keywords = self.agent.get_keywords()
        assert "차량" in keywords
        assert "정비" in keywords

    def test_get_tools(self):
        tools = self.agent.get_tools()
        tool_names = [t.name for t in tools]
        assert "fms_vehicle_status" in tool_names


class TestTAPAgent:
    """TAP! 에이전트 테스트"""

    def setup_method(self):
        self.mock_service = Mock()
        self.agent = TAPAgent(graphrag_service=self.mock_service)

    def test_domain(self):
        assert self.agent.domain == DomainType.TAP

    def test_keywords(self):
        keywords = self.agent.get_keywords()
        assert "호출" in keywords
        assert "ETA" in keywords

    def test_get_tools(self):
        tools = self.agent.get_tools()
        tool_names = [t.name for t in tools]
        assert "tap_call_status" in tool_names


class TestDomainAgentResult:
    """DomainAgentResult 데이터클래스 테스트"""

    def test_basic_result(self):
        """기본 결과 생성"""
        result = DomainAgentResult(
            answer="테스트 답변",
            domain=DomainType.TMS
        )
        assert result.answer == "테스트 답변"
        assert result.domain == DomainType.TMS
        assert result.iterations == 0

    def test_result_with_metadata(self):
        """메타데이터 포함 결과"""
        result = DomainAgentResult(
            answer="테스트",
            domain=DomainType.WMS,
            thoughts=["1단계 분석", "2단계 실행"],
            tool_calls=[{"name": "test", "args": {}}],
            iterations=2,
            metadata={"custom": "data"}
        )
        assert len(result.thoughts) == 2
        assert len(result.tool_calls) == 1
        assert result.metadata["custom"] == "data"
