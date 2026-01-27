"""
WMS (Warehouse Management System) Agent Module

창고 관리 시스템 전문 에이전트입니다.
재고 조회, 적재율, 입출고, 보관 위치 등의 쿼리를 처리합니다.

Usage:
    from genai_fundamentals.api.multi_agents.wms import WMSAgent

    wms_agent = WMSAgent(graphrag_service)
    result = wms_agent.query("창고 A의 적재율은?")
"""

from .agent import WMSAgent

__all__ = ["WMSAgent"]
