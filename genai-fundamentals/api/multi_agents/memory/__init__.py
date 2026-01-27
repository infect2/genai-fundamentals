"""
Memory Agent Module

사용자 정보 저장/조회 전문 에이전트입니다.
"기억해", "내 정보", "recall" 등의 쿼리를 처리합니다.

Usage:
    from genai_fundamentals.api.multi_agents.memory import MemoryAgent

    memory_agent = MemoryAgent(graphrag_service)
    result = memory_agent.query("내 차번호는 59구8426이야 기억해")
"""

from .agent import MemoryAgent

__all__ = ["MemoryAgent"]
