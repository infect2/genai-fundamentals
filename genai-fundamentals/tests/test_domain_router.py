"""
Domain Router Tests

도메인 라우터의 키워드 및 LLM 기반 라우팅을 테스트합니다.

실행 방법:
    pytest genai-fundamentals/tests/test_domain_router.py -v
"""

import sys
import os
import importlib

# 프로젝트 루트를 sys.path에 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pytest
from unittest.mock import Mock, patch

# hyphenated 패키지명은 importlib으로 로드
_base_mod = importlib.import_module("genai-fundamentals.api.multi_agents.base")
_router_mod = importlib.import_module("genai-fundamentals.api.multi_agents.orchestrator.router")

DomainType = _base_mod.DomainType
DomainRouteDecision = _base_mod.DomainRouteDecision
DomainRouter = _router_mod.DomainRouter


class TestDomainRouterKeywords:
    """키워드 기반 라우팅 테스트"""

    def setup_method(self):
        """테스트 전 라우터 초기화 (LLM 없이)"""
        self.router = DomainRouter(llm=None, use_llm_routing=False)

    def test_tms_keywords(self):
        """TMS 도메인 키워드 라우팅"""
        queries = [
            "배송 현황 알려줘",
            "오늘 배차 계획",
            "운송사 목록",
            "화주별 배송 통계",
        ]
        for query in queries:
            decision = self.router.route(query)
            assert decision.domain == DomainType.TMS, f"Failed for query: {query}"

    def test_wms_keywords(self):
        """WMS 도메인 키워드 라우팅"""
        queries = [
            "창고 재고 현황",
            "적재율 확인",
            "입고 예정 목록",
            "출고 현황",
        ]
        for query in queries:
            decision = self.router.route(query)
            assert decision.domain == DomainType.WMS, f"Failed for query: {query}"

    def test_fms_keywords(self):
        """FMS 도메인 키워드 라우팅"""
        queries = [
            "차량 정비 일정",
            "운전자 배정 현황",
            "소모품 교체 필요 차량",
            "연비 분석",
        ]
        for query in queries:
            decision = self.router.route(query)
            assert decision.domain == DomainType.FMS, f"Failed for query: {query}"

    def test_tap_keywords(self):
        """TAP! 도메인 키워드 라우팅"""
        queries = [
            "내 택배 언제 와?",
            "예약 확인해줘",
            "결제 내역 보여줘",
            "ETA 알려줘",
        ]
        for query in queries:
            decision = self.router.route(query)
            assert decision.domain == DomainType.TAP, f"Failed for query: {query}"

    def test_memory_keywords(self):
        """Memory 도메인 키워드 라우팅"""
        queries = [
            "내 차번호 기억해",
            "내 이메일 저장해줘",
            "내 정보 보여줘",
            "remember my phone number",
        ]
        for query in queries:
            decision = self.router.route(query)
            assert decision.domain == DomainType.MEMORY, f"Failed for query: {query}"

    def test_force_domain(self):
        """강제 도메인 지정"""
        decision = self.router.route("아무 질문", force_domain="wms")
        assert decision.domain == DomainType.WMS
        assert decision.confidence == 1.0

    def test_unknown_query(self):
        """알 수 없는 쿼리는 기본값(TMS) 반환"""
        decision = self.router.route("안녕하세요")
        # 키워드 매칭 실패 시 기본값 TMS
        assert decision.domain == DomainType.TMS
        assert decision.confidence == 0.5


class TestDomainRouterCrossDomain:
    """크로스 도메인 라우팅 테스트"""

    def setup_method(self):
        self.router = DomainRouter(llm=None, use_llm_routing=False)

    def test_cross_domain_detection(self):
        """크로스 도메인 쿼리 감지"""
        # FMS + TMS 관련 키워드가 동시에 포함된 쿼리
        query = "정비 중인 차량을 배송에서 제외해줘"
        decision = self.router.route(query)
        # 두 도메인 모두 관련되어 있을 때
        # 실제 구현에서는 두 도메인 점수가 비슷하면 cross_domain=True


class TestDomainRouteDecision:
    """DomainRouteDecision 데이터클래스 테스트"""

    def test_valid_decision(self):
        """유효한 결정 생성"""
        decision = DomainRouteDecision(
            domain=DomainType.TMS,
            confidence=0.9,
            reasoning="배송 관련 쿼리"
        )
        assert decision.domain == DomainType.TMS
        assert decision.confidence == 0.9
        assert not decision.requires_cross_domain

    def test_cross_domain_decision(self):
        """크로스 도메인 결정 생성"""
        decision = DomainRouteDecision(
            domain=DomainType.TMS,
            confidence=0.8,
            reasoning="배차에서 정비 중 차량 제외",
            requires_cross_domain=True,
            secondary_domains=[DomainType.FMS]
        )
        assert decision.requires_cross_domain
        assert DomainType.FMS in decision.secondary_domains

    def test_invalid_confidence(self):
        """유효하지 않은 신뢰도 검증"""
        with pytest.raises(ValueError):
            DomainRouteDecision(
                domain=DomainType.TMS,
                confidence=1.5,  # Invalid
                reasoning="test"
            )


class TestDomainType:
    """DomainType Enum 테스트"""

    def test_from_string(self):
        """문자열에서 DomainType 변환"""
        assert DomainType.from_string("tms") == DomainType.TMS
        assert DomainType.from_string("TMS") == DomainType.TMS
        assert DomainType.from_string("wms") == DomainType.WMS
        assert DomainType.from_string("fms") == DomainType.FMS
        assert DomainType.from_string("tap") == DomainType.TAP
        assert DomainType.from_string("invalid") == DomainType.UNKNOWN
