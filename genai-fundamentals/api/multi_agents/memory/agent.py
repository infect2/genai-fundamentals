"""
Memory Agent Module

Memory (사용자 정보 저장/조회) 도메인 에이전트 클래스입니다.
사용자 정보 저장, 조회, 목록 확인 등의 쿼리를 처리합니다.

Usage:
    from genai_fundamentals.api.multi_agents.memory import MemoryAgent

    memory_agent = MemoryAgent(graphrag_service)
    result = memory_agent.query("내 차번호는 59구8426이야 기억해")
"""

import logging
from typing import List, Optional

from langchain_core.tools import BaseTool

from ..base import BaseDomainAgent, DomainType
from .tools import create_memory_tools
from .prompts import MEMORY_SYSTEM_PROMPT

logger = logging.getLogger(__name__)


class MemoryAgent(BaseDomainAgent):
    """
    Memory (사용자 정보 저장/조회) 도메인 에이전트

    사용자가 개인 정보를 저장하거나 이전에 저장한 정보를
    조회하는 요청을 처리합니다.

    Attributes:
        domain: DomainType.MEMORY
        description: 에이전트 설명

    Example:
        memory_agent = MemoryAgent(graphrag_service)
        result = memory_agent.query("내 차번호는 59구8426이야 기억해")
        print(result.answer)
    """

    domain = DomainType.MEMORY
    description = "사용자 정보 저장/조회 전문 에이전트 (기억, 저장, 조회)"

    # Memory 도메인 키워드
    KEYWORDS = [
        # 한국어
        "기억", "저장", "기억해", "기억해줘", "저장해", "저장해줘",
        "내 정보", "내 이메일", "내 차번호", "내 전화번호", "내 이름",
        "내 주소", "알려줘",
        # 영어
        "remember", "store", "recall", "my info", "my email",
        "my phone", "my name", "my address",
    ]

    def __init__(self, graphrag_service=None, model_name: Optional[str] = None):
        """
        MemoryAgent 초기화

        Args:
            graphrag_service: GraphRAGService 인스턴스
            model_name: 사용할 LLM 모델명
        """
        super().__init__(graphrag_service, model_name)
        self._tools: Optional[List[BaseTool]] = None

    def get_tools(self) -> List[BaseTool]:
        """
        Memory 전용 도구 목록 반환

        Returns:
            Memory 도구 리스트
        """
        if self._tools is None:
            if self._graphrag_service is None:
                logger.warning("GraphRAGService not provided, tools will be empty")
                return []
            self._tools = create_memory_tools(self._graphrag_service)
        return self._tools

    def get_system_prompt(self) -> str:
        """
        Memory 시스템 프롬프트 반환

        Returns:
            Memory 시스템 프롬프트 문자열
        """
        return MEMORY_SYSTEM_PROMPT

    def get_schema_subset(self) -> str:
        """
        Memory 관련 스키마 반환

        Returns:
            UserMemory 노드 스키마 문자열
        """
        return """
## UserMemory 스키마

### 노드
- UserMemory (session_id, key, value, updated_at)

### 설명
- 세션별로 사용자 정보를 key-value 형태로 저장
- session_id: 세션 식별자
- key: 정보 종류 (예: 차번호, 이메일)
- value: 저장된 값
- updated_at: 최종 수정 시간
"""

    def get_keywords(self) -> List[str]:
        """
        Memory 도메인 키워드 목록 반환

        Returns:
            키워드 리스트
        """
        return self.KEYWORDS

    @classmethod
    def is_relevant_query(cls, query: str) -> bool:
        """
        쿼리가 Memory 도메인과 관련있는지 간단히 확인

        Args:
            query: 사용자 쿼리

        Returns:
            관련 여부
        """
        query_lower = query.lower()
        return any(keyword in query_lower for keyword in cls.KEYWORDS)
