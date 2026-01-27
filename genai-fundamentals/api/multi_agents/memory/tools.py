"""
Memory Agent Tools Module

Memory (사용자 정보 저장/조회) 도메인 전용 도구를 정의합니다.
기존 v1 pipelines/memory.py 로직을 재사용합니다.

Tools:
- store_memory: 사용자 정보 저장
- recall_memory: 사용자 정보 조회
- list_memories: 전체 저장 정보 조회

Usage:
    from genai_fundamentals.api.multi_agents.memory.tools import create_memory_tools

    tools = create_memory_tools(graphrag_service)
"""

import json
import logging
from typing import List, Optional
from langchain_core.tools import tool, BaseTool

logger = logging.getLogger(__name__)


def create_memory_tools(graphrag_service) -> List[BaseTool]:
    """
    Memory 도메인 전용 도구 생성

    Args:
        graphrag_service: GraphRAGService 인스턴스

    Returns:
        Memory 전용 도구 리스트
    """

    @tool
    def store_memory(key: str, value: str, session_id: str = "default") -> str:
        """
        사용자 정보를 저장합니다.

        사용자가 기억시키고 싶은 정보를 key-value 형태로 Neo4j에 저장합니다.

        Args:
            key: 정보 종류 (예: "차번호", "이메일", "전화번호", "이름")
            value: 저장할 값 (예: "59구8426", "test@example.com")
            session_id: 세션 ID

        Returns:
            저장 결과 메시지
        """
        try:
            from ...pipelines.memory import store_user_memory

            graph = graphrag_service.graph
            store_user_memory(graph, session_id, key, value)
            return f"'{key}' 정보를 기억했습니다: {value}"

        except Exception as e:
            logger.error(f"store_memory error: {e}")
            return f"정보 저장 중 오류 발생: {str(e)}"

    @tool
    def recall_memory(key: str, session_id: str = "default") -> str:
        """
        이전에 저장한 사용자 정보를 조회합니다.

        Args:
            key: 조회할 정보 종류 (예: "차번호", "이메일", "전화번호")
            session_id: 세션 ID

        Returns:
            저장된 값 또는 없음 메시지
        """
        try:
            from ...pipelines.memory import get_user_memory

            graph = graphrag_service.graph
            stored_value = get_user_memory(graph, session_id, key)
            if stored_value:
                return f"{key}은(는) {stored_value}입니다."
            else:
                return f"저장된 '{key}' 정보가 없습니다."

        except Exception as e:
            logger.error(f"recall_memory error: {e}")
            return f"정보 조회 중 오류 발생: {str(e)}"

    @tool
    def list_memories(session_id: str = "default") -> str:
        """
        세션에 저장된 모든 사용자 정보 목록을 조회합니다.

        Args:
            session_id: 세션 ID

        Returns:
            저장된 모든 정보 목록
        """
        try:
            from ...pipelines.memory import get_all_user_memories

            graph = graphrag_service.graph
            memories = get_all_user_memories(graph, session_id)

            if not memories:
                return "저장된 정보가 없습니다."

            output = f"## 저장된 정보 ({len(memories)}건)\n\n"
            for i, mem in enumerate(memories, 1):
                output += f"{i}. **{mem['key']}**: {mem['value']}\n"

            return output

        except Exception as e:
            logger.error(f"list_memories error: {e}")
            return f"정보 목록 조회 중 오류 발생: {str(e)}"

    return [
        store_memory,
        recall_memory,
        list_memories,
    ]
