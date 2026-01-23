"""
GraphRAG 데이터 모델 정의

API 전반에서 사용되는 데이터 클래스들을 정의합니다.
"""

import asyncio
from dataclasses import dataclass
from typing import Optional, List

from langchain_core.callbacks import BaseCallbackHandler


# =============================================================================
# 데이터 클래스 정의
# =============================================================================

@dataclass
class TokenUsage:
    """
    LLM 토큰 사용량을 담는 데이터 클래스

    Attributes:
        total_tokens: 총 토큰 수
        prompt_tokens: 프롬프트 토큰 수
        completion_tokens: 완성 토큰 수
        total_cost: 총 비용 (USD)
    """
    total_tokens: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_cost: float = 0.0


@dataclass
class QueryResult:
    """
    쿼리 실행 결과를 담는 데이터 클래스

    Attributes:
        answer: LLM이 생성한 자연어 답변
        cypher: 생성된 Cypher 쿼리
        context: Neo4j에서 가져온 원본 데이터 리스트
        route: 사용된 라우트 타입 (cypher, vector, hybrid, llm_only, memory)
        route_reasoning: 라우팅 결정 이유
        token_usage: LLM 토큰 사용량
    """
    answer: str
    cypher: str
    context: List[str]
    route: str = ""
    route_reasoning: str = ""
    token_usage: Optional[TokenUsage] = None


# =============================================================================
# 스트리밍 콜백 핸들러
# =============================================================================

class StreamingCallbackHandler(BaseCallbackHandler):
    """
    LLM의 스트리밍 출력을 처리하는 콜백 핸들러

    LangChain의 콜백 시스템을 활용해 LLM이 토큰을 생성할 때마다
    실시간으로 처리할 수 있습니다.
    """

    def __init__(self):
        self.tokens = []
        self.queue = asyncio.Queue()
        self.done = False

    def on_llm_new_token(self, token: str, **kwargs):
        """새 토큰이 생성될 때마다 호출"""
        self.tokens.append(token)
        asyncio.get_event_loop().call_soon_threadsafe(
            self.queue.put_nowait, token
        )

    def on_llm_end(self, response, **kwargs):
        """LLM 생성 완료 시 호출"""
        self.done = True
        asyncio.get_event_loop().call_soon_threadsafe(
            self.queue.put_nowait, None
        )
