"""
TAP! Agent Module

TAP! (사용자 호출 서비스) 도메인 에이전트 클래스입니다.
"""

import logging
from typing import List, Optional

from langchain_core.tools import BaseTool

from ..base import BaseDomainAgent, DomainType
from .tools import create_tap_tools
from .prompts import TAP_SYSTEM_PROMPT

logger = logging.getLogger(__name__)


class TAPAgent(BaseDomainAgent):
    """
    TAP! (사용자 호출 서비스) 도메인 에이전트

    사용자의 호출 요청, 예약, ETA 조회, 결제, 피드백 등의
    질문에 친절하게 답변합니다.
    """

    domain = DomainType.TAP
    description = "사용자 호출 서비스 전문 에이전트 (호출, ETA, 예약, 결제)"

    KEYWORDS = [
        "호출", "예약", "ETA", "도착 예정", "결제", "피드백",
        "내 택배", "내 배송", "언제 와", "예약 확인", "결제 내역",
        "call", "booking", "payment", "eta", "arrival",
    ]

    def __init__(self, graphrag_service=None, model_name: Optional[str] = None):
        super().__init__(graphrag_service, model_name)
        self._tools: Optional[List[BaseTool]] = None

    def get_tools(self) -> List[BaseTool]:
        if self._tools is None:
            if self._graphrag_service is None:
                return []
            self._tools = create_tap_tools(self._graphrag_service)
        return self._tools

    def get_system_prompt(self) -> str:
        return TAP_SYSTEM_PROMPT

    def get_schema_subset(self) -> str:
        from ...ontology.tap_schema import get_tap_schema
        return get_tap_schema()

    def get_keywords(self) -> List[str]:
        return self.KEYWORDS
