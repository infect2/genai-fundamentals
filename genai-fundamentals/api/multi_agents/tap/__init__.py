"""
TAP! Agent Module

TAP! 사용자 호출 서비스 전문 에이전트입니다.
차량 호출, ETA 조회, 결제, 피드백 등의 쿼리를 처리합니다.

Usage:
    from genai_fundamentals.api.multi_agents.tap import TAPAgent

    tap_agent = TAPAgent(graphrag_service)
    result = tap_agent.query("내 택배 언제 와?")
"""

from .agent import TAPAgent

__all__ = ["TAPAgent"]
