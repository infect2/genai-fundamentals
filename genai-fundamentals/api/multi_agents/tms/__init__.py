"""
TMS (Transportation Management System) Agent Module

운송 관리 시스템 전문 에이전트입니다.
배송 현황, 경로 최적화, 배차, 운송 지연 등의 쿼리를 처리합니다.

Usage:
    from genai_fundamentals.api.multi_agents.tms import TMSAgent

    tms_agent = TMSAgent(graphrag_service)
    result = tms_agent.query("오늘 배송 현황 알려줘")
"""

from .agent import TMSAgent

__all__ = ["TMSAgent"]
