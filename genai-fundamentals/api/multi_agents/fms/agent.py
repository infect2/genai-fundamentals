"""
FMS Agent Module

FMS (차량 관리 시스템) 도메인 에이전트 클래스입니다.
"""

import logging
from typing import List, Optional

from langchain_core.tools import BaseTool

from ..base import BaseDomainAgent, DomainType
from .tools import create_fms_tools
from .prompts import FMS_SYSTEM_PROMPT

logger = logging.getLogger(__name__)


class FMSAgent(BaseDomainAgent):
    """
    FMS (Fleet Management System) 도메인 에이전트

    차량 관리 관련 질문에 답변하고, 차량 상태, 정비 일정,
    운전자 관리, 소모품 상태 등의 업무를 수행합니다.
    """

    domain = DomainType.FMS
    description = "차량 관리 시스템 전문 에이전트 (차량, 정비, 운전자, 소모품)"

    KEYWORDS = [
        "차량", "정비", "소모품", "운전자", "연비", "주유", "타이어", "엔진",
        "차량 상태", "정비 일정", "면허", "오일", "브레이크", "배터리",
        "vehicle", "maintenance", "driver", "fleet", "fuel", "tire",
    ]

    def __init__(self, graphrag_service=None, model_name: Optional[str] = None):
        super().__init__(graphrag_service, model_name)
        self._tools: Optional[List[BaseTool]] = None

    def get_tools(self) -> List[BaseTool]:
        if self._tools is None:
            if self._graphrag_service is None:
                return []
            self._tools = create_fms_tools(self._graphrag_service)
        return self._tools

    def get_system_prompt(self) -> str:
        return FMS_SYSTEM_PROMPT

    def get_schema_subset(self) -> str:
        from ...ontology.fms_schema import get_fms_schema
        return get_fms_schema()

    def get_keywords(self) -> List[str]:
        return self.KEYWORDS
