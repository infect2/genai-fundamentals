"""
FMS (Fleet Management System) Agent Module

차량 관리 시스템 전문 에이전트입니다.
차량 상태, 정비 일정, 소모품, 운전자 관리 등의 쿼리를 처리합니다.

Usage:
    from genai_fundamentals.api.multi_agents.fms import FMSAgent

    fms_agent = FMSAgent(graphrag_service)
    result = fms_agent.query("정비 예정인 차량 목록")
"""

from .agent import FMSAgent

__all__ = ["FMSAgent"]
