"""
TMS Agent Module

TMS (운송 관리 시스템) 도메인 에이전트 클래스입니다.
배송 현황, 경로 최적화, 배차 관리, 운송사 검색 등의 쿼리를 처리합니다.

Usage:
    from genai_fundamentals.api.multi_agents.tms import TMSAgent

    tms_agent = TMSAgent(graphrag_service)
    result = tms_agent.query("오늘 배송 현황 알려줘")
"""

import logging
from typing import List, Optional

from langchain_core.tools import BaseTool

from ..base import BaseDomainAgent, DomainType
from .tools import create_tms_tools
from .prompts import TMS_SYSTEM_PROMPT

logger = logging.getLogger(__name__)


class TMSAgent(BaseDomainAgent):
    """
    TMS (Transportation Management System) 도메인 에이전트

    물류 운송 관련 질문에 답변하고, 배송 현황, 경로 최적화,
    배차 관리, 운송사 검색 등의 업무를 수행합니다.

    Attributes:
        domain: DomainType.TMS
        description: 에이전트 설명

    Example:
        tms_agent = TMSAgent(graphrag_service)
        result = tms_agent.query("운송 중인 배송 목록")
        print(result.answer)
    """

    domain = DomainType.TMS
    description = "운송 관리 시스템 전문 에이전트 (배송, 배차, 운송사, 경로)"

    # TMS 도메인 키워드
    KEYWORDS = [
        # 한국어
        "배송", "배차", "운송", "운송사", "화주", "경로", "출발지", "목적지",
        "픽업", "도착", "지연", "운임", "화물", "shipment", "배달",
        "물류센터", "항구", "터미널", "차량 배정", "운송 현황",
        # 영어
        "shipment", "delivery", "dispatch", "carrier", "shipper",
        "route", "origin", "destination", "pickup", "freight",
        "logistics", "transport", "shipping",
    ]

    def __init__(self, graphrag_service=None, model_name: Optional[str] = None):
        """
        TMSAgent 초기화

        Args:
            graphrag_service: GraphRAGService 인스턴스
            model_name: 사용할 LLM 모델명
        """
        super().__init__(graphrag_service, model_name)
        self._tools: Optional[List[BaseTool]] = None

    def get_tools(self) -> List[BaseTool]:
        """
        TMS 전용 도구 목록 반환

        Returns:
            TMS 도구 리스트
        """
        if self._tools is None:
            if self._graphrag_service is None:
                logger.warning("GraphRAGService not provided, tools will be empty")
                return []
            self._tools = create_tms_tools(self._graphrag_service)
        return self._tools

    def get_system_prompt(self) -> str:
        """
        TMS 시스템 프롬프트 반환

        Returns:
            TMS 시스템 프롬프트 문자열
        """
        return TMS_SYSTEM_PROMPT

    def get_schema_subset(self) -> str:
        """
        TMS 관련 온톨로지 스키마 반환

        Returns:
            TMS TBox 스키마 문자열
        """
        from ...ontology.tms_schema import get_tms_schema
        return get_tms_schema()

    def get_keywords(self) -> List[str]:
        """
        TMS 도메인 키워드 목록 반환

        Returns:
            키워드 리스트
        """
        return self.KEYWORDS

    @classmethod
    def is_relevant_query(cls, query: str) -> bool:
        """
        쿼리가 TMS 도메인과 관련있는지 간단히 확인

        Args:
            query: 사용자 쿼리

        Returns:
            관련 여부
        """
        query_lower = query.lower()
        return any(keyword in query_lower for keyword in cls.KEYWORDS)
