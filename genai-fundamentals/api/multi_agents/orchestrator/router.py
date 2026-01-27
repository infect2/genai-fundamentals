"""
Domain Router Module

사용자 쿼리를 분석하여 적합한 도메인 에이전트로 라우팅합니다.
LLM 기반 의도 분석과 키워드 기반 빠른 라우팅을 지원합니다.

Usage:
    from genai_fundamentals.api.multi_agents.orchestrator.router import DomainRouter

    router = DomainRouter(llm)
    decision = router.route("배송 현황 알려줘")
"""

import json
import logging
from typing import Optional, List

from langchain_core.language_models import BaseChatModel
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

from ..base import DomainType, DomainRouteDecision
from ..registry import get_registry
from .prompts import DOMAIN_CLASSIFICATION_PROMPT

logger = logging.getLogger(__name__)


class DomainRouter:
    """
    도메인 라우터

    사용자 쿼리를 분석하여 가장 적합한 도메인 에이전트로 라우팅합니다.
    LLM 기반 의도 분석과 키워드 기반 빠른 라우팅을 지원합니다.

    Attributes:
        llm: 의도 분석에 사용할 LLM
        use_llm_routing: LLM 라우팅 사용 여부
    """

    # 도메인별 키워드 (빠른 라우팅용)
    DOMAIN_KEYWORDS = {
        DomainType.WMS: [
            "창고", "재고", "적재", "입고", "출고", "보관", "피킹", "적치",
            "재고량", "재고 현황", "warehouse", "inventory", "stock",
        ],
        DomainType.TMS: [
            "배송", "배차", "운송", "운송사", "화주", "경로", "출발지", "목적지",
            "픽업", "배달", "물류센터", "항구", "shipment", "delivery", "dispatch",
            "carrier", "shipper", "route",
        ],
        DomainType.FMS: [
            "차량", "정비", "소모품", "운전자", "연비", "주유", "타이어", "엔진",
            "차량 상태", "정비 일정", "vehicle", "maintenance", "driver", "fleet",
        ],
        DomainType.TAP: [
            "호출", "예약", "ETA", "도착 예정", "결제", "피드백",
            "내 택배", "내 배송", "언제 와", "call", "booking", "payment",
        ],
        DomainType.MEMORY: [
            "기억", "저장", "기억해", "기억해줘", "저장해", "저장해줘",
            "내 정보", "내 이메일", "내 차번호", "내 전화번호", "내 이름",
            "내 주소", "remember", "store", "recall",
        ],
    }

    def __init__(
        self,
        llm: Optional[BaseChatModel] = None,
        use_llm_routing: bool = True
    ):
        """
        DomainRouter 초기화

        Args:
            llm: 의도 분석에 사용할 LLM (None이면 키워드 라우팅만 사용)
            use_llm_routing: LLM 라우팅 사용 여부
        """
        self._llm = llm
        self._use_llm_routing = use_llm_routing and llm is not None

        if self._llm:
            self._prompt = ChatPromptTemplate.from_template(DOMAIN_CLASSIFICATION_PROMPT)
            self._chain = self._prompt | self._llm | StrOutputParser()

    def route(
        self,
        query: str,
        history_summary: str = "",
        force_domain: Optional[str] = None
    ) -> DomainRouteDecision:
        """
        쿼리를 적합한 도메인으로 라우팅

        Args:
            query: 사용자 쿼리
            history_summary: 대화 이력 요약 (옵션)
            force_domain: 강제 도메인 지정 (옵션)

        Returns:
            DomainRouteDecision 객체
        """
        # 강제 도메인 지정
        if force_domain:
            domain = DomainType.from_string(force_domain)
            return DomainRouteDecision(
                domain=domain,
                confidence=1.0,
                reasoning=f"강제 도메인 지정: {force_domain}",
                requires_cross_domain=False,
                secondary_domains=[]
            )

        # 1. 키워드 기반 빠른 라우팅 시도
        keyword_result = self._route_by_keywords(query)
        if keyword_result and keyword_result.confidence >= 0.8:
            logger.debug(f"Keyword routing: {keyword_result.domain.value} (confidence: {keyword_result.confidence})")
            return keyword_result

        # 2. LLM 기반 의도 분석
        if self._use_llm_routing:
            try:
                llm_result = self._route_by_llm(query, history_summary)
                if llm_result:
                    logger.debug(f"LLM routing: {llm_result.domain.value} (confidence: {llm_result.confidence})")
                    return llm_result
            except Exception as e:
                logger.warning(f"LLM routing failed, falling back to keyword: {e}")

        # 3. 키워드 결과 반환 (낮은 신뢰도라도)
        if keyword_result:
            return keyword_result

        # 4. 기본값: TMS (가장 일반적인 물류 도메인)
        return DomainRouteDecision(
            domain=DomainType.TMS,
            confidence=0.5,
            reasoning="도메인을 명확히 판단할 수 없어 기본값(TMS) 사용",
            requires_cross_domain=False,
            secondary_domains=[]
        )

    async def route_async(
        self,
        query: str,
        history_summary: str = "",
        force_domain: Optional[str] = None
    ) -> DomainRouteDecision:
        """비동기 라우팅"""
        # 강제 도메인 지정
        if force_domain:
            domain = DomainType.from_string(force_domain)
            return DomainRouteDecision(
                domain=domain,
                confidence=1.0,
                reasoning=f"강제 도메인 지정: {force_domain}",
                requires_cross_domain=False,
                secondary_domains=[]
            )

        # 키워드 라우팅 (동기)
        keyword_result = self._route_by_keywords(query)
        if keyword_result and keyword_result.confidence >= 0.8:
            return keyword_result

        # LLM 라우팅 (비동기)
        if self._use_llm_routing:
            try:
                llm_result = await self._route_by_llm_async(query, history_summary)
                if llm_result:
                    return llm_result
            except Exception as e:
                logger.warning(f"Async LLM routing failed: {e}")

        if keyword_result:
            return keyword_result

        return DomainRouteDecision(
            domain=DomainType.TMS,
            confidence=0.5,
            reasoning="도메인을 명확히 판단할 수 없어 기본값(TMS) 사용",
            requires_cross_domain=False,
            secondary_domains=[]
        )

    def _route_by_keywords(self, query: str) -> Optional[DomainRouteDecision]:
        """키워드 기반 빠른 라우팅"""
        query_lower = query.lower()
        domain_scores = {}

        for domain, keywords in self.DOMAIN_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw.lower() in query_lower)
            if score > 0:
                domain_scores[domain] = score

        if not domain_scores:
            return None

        # 가장 높은 점수의 도메인 선택
        best_domain = max(domain_scores, key=domain_scores.get)
        best_score = domain_scores[best_domain]
        total_score = sum(domain_scores.values())

        # 신뢰도 계산 (상대적 점수)
        confidence = best_score / max(total_score, 1) * min(best_score / 2, 1.0)

        # 크로스 도메인 판단 (두 번째로 높은 도메인이 있으면)
        secondary_domains = []
        requires_cross_domain = False

        if len(domain_scores) > 1:
            sorted_domains = sorted(domain_scores.items(), key=lambda x: x[1], reverse=True)
            second_domain, second_score = sorted_domains[1]
            if second_score >= best_score * 0.5:  # 50% 이상이면 크로스 도메인
                requires_cross_domain = True
                secondary_domains = [second_domain]

        return DomainRouteDecision(
            domain=best_domain,
            confidence=min(confidence, 1.0),
            reasoning=f"키워드 매칭: {best_score}개 일치",
            requires_cross_domain=requires_cross_domain,
            secondary_domains=secondary_domains
        )

    def _route_by_llm(self, query: str, history_summary: str = "") -> Optional[DomainRouteDecision]:
        """LLM 기반 의도 분석 (동기)"""
        try:
            result = self._chain.invoke({
                "query": query,
                "history_summary": history_summary or "없음"
            })
            return self._parse_llm_response(result)
        except Exception as e:
            logger.error(f"LLM routing error: {e}")
            return None

    async def _route_by_llm_async(self, query: str, history_summary: str = "") -> Optional[DomainRouteDecision]:
        """LLM 기반 의도 분석 (비동기)"""
        try:
            result = await self._chain.ainvoke({
                "query": query,
                "history_summary": history_summary or "없음"
            })
            return self._parse_llm_response(result)
        except Exception as e:
            logger.error(f"Async LLM routing error: {e}")
            return None

    def _parse_llm_response(self, response: str) -> Optional[DomainRouteDecision]:
        """LLM 응답 파싱"""
        try:
            # JSON 블록 추출
            if "```json" in response:
                json_str = response.split("```json")[1].split("```")[0].strip()
            elif "```" in response:
                json_str = response.split("```")[1].split("```")[0].strip()
            else:
                json_str = response.strip()

            data = json.loads(json_str)

            domain = DomainType.from_string(data.get("domain", "unknown"))
            secondary_domains = [
                DomainType.from_string(d)
                for d in data.get("secondary_domains", [])
            ]

            return DomainRouteDecision(
                domain=domain,
                confidence=float(data.get("confidence", 0.5)),
                reasoning=data.get("reasoning", ""),
                requires_cross_domain=data.get("cross_domain", False),
                secondary_domains=secondary_domains
            )
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.warning(f"Failed to parse LLM response: {e}")
            return None
