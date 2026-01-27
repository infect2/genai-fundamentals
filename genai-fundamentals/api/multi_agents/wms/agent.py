"""
WMS Agent Module

WMS (창고 관리 시스템) 도메인 에이전트 클래스입니다.
"""

import logging
from typing import List, Optional

from langchain_core.tools import BaseTool

from ..base import BaseDomainAgent, DomainType
from .tools import create_wms_tools
from .prompts import WMS_SYSTEM_PROMPT

logger = logging.getLogger(__name__)


class WMSAgent(BaseDomainAgent):
    """
    WMS (Warehouse Management System) 도메인 에이전트

    창고 관리 관련 질문에 답변하고, 재고 조회, 적재율 확인,
    입출고 현황 등의 업무를 수행합니다.
    """

    domain = DomainType.WMS
    description = "창고 관리 시스템 전문 에이전트 (재고, 적재율, 입출고)"

    KEYWORDS = [
        "창고", "재고", "적재", "입고", "출고", "보관", "피킹", "적치",
        "재고량", "재고 현황", "적재율", "로케이션", "빈", "SKU",
        "warehouse", "inventory", "stock", "bin", "zone",
    ]

    def __init__(self, graphrag_service=None, model_name: Optional[str] = None):
        super().__init__(graphrag_service, model_name)
        self._tools: Optional[List[BaseTool]] = None

    def get_tools(self) -> List[BaseTool]:
        if self._tools is None:
            if self._graphrag_service is None:
                return []
            self._tools = create_wms_tools(self._graphrag_service)
        return self._tools

    def get_system_prompt(self) -> str:
        return WMS_SYSTEM_PROMPT

    def get_schema_subset(self) -> str:
        from ...ontology.wms_schema import get_wms_schema
        return get_wms_schema()

    def get_keywords(self) -> List[str]:
        return self.KEYWORDS
