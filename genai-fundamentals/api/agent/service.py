"""
Agent Service Module

AgentService는 ReAct Agent의 통합 인터페이스를 제공합니다.
기존 GraphRAGService와 LangGraph Agent를 연결합니다.

Performance Optimizations:
- Query result caching (LRU with TTL)
- Schema caching
- Concurrent request handling
- Request coalescing (동일 쿼리 동시 요청 병합)
- LLM semaphore (동시 API 호출 제한)
"""

import json
import asyncio
import hashlib
import logging
from dataclasses import dataclass, asdict
from typing import Optional, List, AsyncGenerator, Any

from langchain_core.messages import HumanMessage, AIMessage, ToolMessage

from ...tools.llm_provider import get_token_tracker

from .graph import create_agent_graph
from .state import AgentState
from ..models import TokenUsage
from ..cache import get_cache, get_coalescer, get_llm_semaphore, QueryCache

logger = logging.getLogger(__name__)


@dataclass
class AgentResult:
    """
    Agent 실행 결과를 담는 데이터 클래스

    Attributes:
        answer: 최종 답변
        thoughts: Agent의 추론 과정 (thinking steps)
        tool_calls: 호출된 도구 목록
        tool_results: 도구 실행 결과 목록
        iterations: 총 반복 횟수
        token_usage: LLM 토큰 사용량
    """
    answer: str
    thoughts: List[str]
    tool_calls: List[dict]
    tool_results: List[dict]
    iterations: int
    token_usage: Optional[TokenUsage] = None


class AgentService:
    """
    ReAct Agent 서비스 클래스

    LangGraph 기반 ReAct Agent를 사용하여
    multi-step reasoning을 통해 복잡한 쿼리를 처리합니다.

    사용 예:
        from genai_fundamentals.api.graphrag_service import GraphRAGService
        from genai_fundamentals.api.agent import AgentService

        ontology_service = GraphRAGService()
        agent_service = AgentService(ontology_service)
        result = agent_service.query("Find entities connected to X with similar properties")
        print(result.answer)
    """

    def __init__(
        self,
        graphrag_service,
        model_name: Optional[str] = None,
        enable_cache: bool = True,
        cache_ttl: float = 300,  # 5 minutes
        max_concurrent_llm: int = 10  # 최대 동시 LLM 호출 수
    ):
        """
        AgentService 초기화

        Args:
            graphrag_service: GraphRAGService 인스턴스
            model_name: Agent에서 사용할 LLM 모델 (기본값: 프로바이더별 환경변수)
            enable_cache: 캐싱 활성화 여부
            cache_ttl: 캐시 TTL (초)
            max_concurrent_llm: 최대 동시 LLM API 호출 수 (기본: 10)
        """
        self._graphrag_service = graphrag_service
        self._model_name = model_name
        self._graph = create_agent_graph(graphrag_service, model_name)
        self._enable_cache = enable_cache
        self._cache_ttl = cache_ttl
        self._cache: QueryCache = get_cache() if enable_cache else None

        # 동시성 최적화
        self._coalescer = get_coalescer()
        self._semaphore = get_llm_semaphore(max_concurrent_llm)

    def query(
        self,
        query_text: str,
        session_id: str = "default",
        use_cache: bool = True
    ) -> AgentResult:
        """
        자연어 쿼리 실행 (동기 방식)

        ReAct Agent를 사용하여 multi-step reasoning으로
        복잡한 쿼리를 처리합니다.

        Args:
            query_text: 사용자 질문
            session_id: 세션 ID (기본값: "default")
            use_cache: 캐시 사용 여부 (기본값: True)

        Returns:
            AgentResult 객체
        """
        # 캐시 확인
        if use_cache and self._cache:
            cached = self._cache.get(query_text, session_id)
            if cached is not None:
                # 캐시 히트 - 저장된 결과 반환
                return self._dict_to_result(cached)

        # 초기 상태 설정
        initial_state: AgentState = {
            "messages": [HumanMessage(content=query_text)],
            "session_id": session_id,
            "tool_results": [],
            "iteration": 0,
            "final_answer": None
        }

        # 그래프 실행 (토큰 사용량 추적)
        with get_token_tracker() as cb:
            final_state = self._graph.invoke(initial_state)

        # 결과 추출
        result = self._extract_result(final_state)
        result.token_usage = TokenUsage(
            total_tokens=cb.total_tokens,
            prompt_tokens=cb.prompt_tokens,
            completion_tokens=cb.completion_tokens,
            total_cost=cb.total_cost
        )

        # 캐시 저장
        if use_cache and self._cache:
            self._cache.set(query_text, session_id, self._result_to_dict(result), self._cache_ttl)

        # 대화 이력 저장 (Neo4j에 영속화)
        self._save_to_history(session_id, query_text, result.answer)

        return result

    async def query_async(
        self,
        query_text: str,
        session_id: str = "default",
        use_cache: bool = True
    ) -> AgentResult:
        """
        자연어 쿼리 실행 (비동기 방식, 동시성 최적화)

        Features:
        - 캐시 히트 시 즉시 반환
        - Request Coalescing: 동일 쿼리 동시 요청 병합
        - LLM Semaphore: 동시 API 호출 수 제한

        Args:
            query_text: 사용자 질문
            session_id: 세션 ID
            use_cache: 캐시 사용 여부

        Returns:
            AgentResult 객체
        """
        # 1. 캐시 확인 (가장 빠른 경로)
        if use_cache and self._cache:
            cached = self._cache.get(query_text, session_id)
            if cached is not None:
                logger.debug(f"Cache hit for query: {query_text[:50]}...")
                return self._dict_to_result(cached)

        # 2. 쿼리 키 생성 (coalescing용)
        query_key = self._make_query_key(query_text, session_id)

        # 3. Request Coalescing + Semaphore를 사용한 실행
        async def execute_query():
            # Semaphore로 동시 LLM 호출 제한
            async with await self._semaphore.acquire():
                logger.debug(f"Executing query with semaphore: {query_text[:50]}...")

                # 초기 상태 설정
                initial_state: AgentState = {
                    "messages": [HumanMessage(content=query_text)],
                    "session_id": session_id,
                    "tool_results": [],
                    "iteration": 0,
                    "final_answer": None
                }

                # 비동기 그래프 실행 (토큰 사용량 추적)
                with get_token_tracker() as cb:
                    final_state = await self._graph.ainvoke(initial_state)

                # 결과 추출
                result = self._extract_result(final_state)
                result.token_usage = TokenUsage(
                    total_tokens=cb.total_tokens,
                    prompt_tokens=cb.prompt_tokens,
                    completion_tokens=cb.completion_tokens,
                    total_cost=cb.total_cost
                )

                # 캐시 저장
                if use_cache and self._cache:
                    self._cache.set(query_text, session_id, self._result_to_dict(result), self._cache_ttl)

                # 대화 이력 저장 (Neo4j에 영속화)
                self._save_to_history(session_id, query_text, result.answer)

                return result

        # Coalescing: 동일 쿼리 동시 요청 병합
        result = await self._coalescer.execute(query_key, execute_query)
        return result

    def _make_query_key(self, query_text: str, session_id: str) -> str:
        """쿼리 키 생성 (coalescing용)"""
        # 캐시와 동일한 정규화 로직 사용
        if self._cache:
            return self._cache._make_key(query_text, session_id)
        return hashlib.md5(f"{query_text}:{session_id}".encode()).hexdigest()

    async def query_stream(
        self,
        query_text: str,
        session_id: str = "default"
    ) -> AsyncGenerator[str, None]:
        """
        SSE 형식으로 스트리밍 응답 생성

        응답 순서:
        1. thought: Agent의 추론 과정
        2. tool_call: 도구 호출 정보
        3. tool_result: 도구 실행 결과
        4. token: 최종 답변 토큰
        5. done: 스트리밍 완료 (토큰 사용량 포함)

        Args:
            query_text: 사용자 질문
            session_id: 세션 ID

        Yields:
            SSE 형식 문자열
        """
        # 초기 상태 설정
        initial_state: AgentState = {
            "messages": [HumanMessage(content=query_text)],
            "session_id": session_id,
            "tool_results": [],
            "iteration": 0,
            "final_answer": None
        }

        final_answer = ""
        tool_calls_sent = set()

        # astream_events를 사용하여 실시간 이벤트 스트리밍 (토큰 사용량 추적)
        with get_token_tracker() as cb:
            async for event in self._graph.astream_events(initial_state, version="v2"):
                event_type = event.get("event", "")
                event_data = event.get("data", {})

                if event_type == "on_chat_model_stream":
                    # LLM 토큰 스트리밍
                    chunk = event_data.get("chunk")
                    if chunk and hasattr(chunk, "content") and chunk.content:
                        yield f"data: {json.dumps({'type': 'token', 'content': chunk.content})}\n\n"

                elif event_type == "on_chat_model_end":
                    # LLM 응답 완료
                    output = event_data.get("output")
                    if output and hasattr(output, "tool_calls") and output.tool_calls:
                        for tc in output.tool_calls:
                            tc_id = tc.get("id", "")
                            if tc_id not in tool_calls_sent:
                                tool_calls_sent.add(tc_id)
                                yield f"data: {json.dumps({'type': 'tool_call', 'tool': tc.get('name', ''), 'input': tc.get('args', {})})}\n\n"

                    elif output and hasattr(output, "content") and output.content:
                        final_answer = output.content

                elif event_type == "on_tool_end":
                    # 도구 실행 완료
                    output = event_data.get("output")
                    if output:
                        # ToolMessage에서 content 추출 (LangChain 메시지 객체인 경우)
                        if hasattr(output, "content"):
                            result_content = output.content
                        elif isinstance(output, str):
                            result_content = output
                        else:
                            result_content = str(output)
                        # 결과가 너무 길면 잘라냄
                        if len(result_content) > 500:
                            result_content = result_content[:500] + "..."
                        yield f"data: {json.dumps({'type': 'tool_result', 'result': result_content})}\n\n"

        # 대화 이력 저장 (Neo4j에 영속화)
        self._save_to_history(session_id, query_text, final_answer)

        # 완료 신호 (토큰 사용량 포함)
        done_data = {"type": "done", "final_answer": final_answer}
        done_data["token_usage"] = {
            "total_tokens": cb.total_tokens,
            "prompt_tokens": cb.prompt_tokens,
            "completion_tokens": cb.completion_tokens,
            "total_cost": cb.total_cost
        }
        yield f"data: {json.dumps(done_data)}\n\n"

    def _extract_result(self, final_state: dict) -> AgentResult:
        """
        최종 상태에서 결과를 추출합니다.

        Args:
            final_state: LangGraph 실행 후 최종 상태

        Returns:
            AgentResult 객체
        """
        messages = final_state.get("messages", [])
        tool_results = final_state.get("tool_results", [])
        iterations = final_state.get("iteration", 0)

        # 최종 답변 추출 (마지막 AIMessage)
        answer = ""
        thoughts = []
        tool_calls = []

        for msg in messages:
            if isinstance(msg, AIMessage):
                if msg.tool_calls:
                    # 도구 호출 기록
                    for tc in msg.tool_calls:
                        tool_calls.append({
                            "name": tc.get("name", ""),
                            "args": tc.get("args", {})
                        })
                elif msg.content:
                    # 최종 답변 또는 중간 추론
                    answer = msg.content
                    thoughts.append(msg.content)

        return AgentResult(
            answer=answer,
            thoughts=thoughts,
            tool_calls=tool_calls,
            tool_results=tool_results,
            iterations=iterations
        )

    def _save_to_history(self, session_id: str, query_text: str, answer: str) -> None:
        """
        대화 이력을 Neo4j에 저장합니다.

        Args:
            session_id: 세션 ID
            query_text: 사용자 질문
            answer: Agent 응답
        """
        try:
            history = self._graphrag_service.get_or_create_history(session_id)
            history.add_user_message(query_text)
            history.add_ai_message(answer)
        except Exception as e:
            # 히스토리 저장 실패는 무시 (로깅만 수행)
            import logging
            logging.getLogger(__name__).warning(f"Failed to save history: {e}")

    def _result_to_dict(self, result: AgentResult) -> dict:
        """AgentResult를 캐시 저장용 dict로 변환"""
        return {
            "answer": result.answer,
            "thoughts": result.thoughts,
            "tool_calls": result.tool_calls,
            "tool_results": result.tool_results,
            "iterations": result.iterations,
            "token_usage": {
                "total_tokens": result.token_usage.total_tokens,
                "prompt_tokens": result.token_usage.prompt_tokens,
                "completion_tokens": result.token_usage.completion_tokens,
                "total_cost": result.token_usage.total_cost
            } if result.token_usage else None,
            "cached": True  # 캐시된 결과임을 표시
        }

    def _dict_to_result(self, data: dict) -> AgentResult:
        """캐시에서 가져온 dict를 AgentResult로 변환"""
        token_usage = None
        if data.get("token_usage"):
            token_usage = TokenUsage(
                total_tokens=data["token_usage"]["total_tokens"],
                prompt_tokens=data["token_usage"]["prompt_tokens"],
                completion_tokens=data["token_usage"]["completion_tokens"],
                total_cost=data["token_usage"]["total_cost"]
            )

        return AgentResult(
            answer=data["answer"],
            thoughts=data["thoughts"],
            tool_calls=data["tool_calls"],
            tool_results=data["tool_results"],
            iterations=data["iterations"],
            token_usage=token_usage
        )

    def get_cache_stats(self) -> dict:
        """캐시 및 동시성 통계 반환"""
        stats = {
            "cache": self._cache.get_stats() if self._cache else {"enabled": False},
            "coalescer": self._coalescer.get_stats() if self._coalescer else {"enabled": False},
            "semaphore": self._semaphore.get_stats() if self._semaphore else {"enabled": False}
        }
        return stats


# =============================================================================
# 싱글톤 인스턴스 (선택적 사용)
# =============================================================================

_agent_service_instance: Optional[AgentService] = None


def get_agent_service(graphrag_service=None) -> AgentService:
    """
    AgentService 싱글톤 인스턴스 반환

    Args:
        graphrag_service: GraphRAGService 인스턴스 (최초 호출 시 필수)

    Returns:
        AgentService 인스턴스
    """
    global _agent_service_instance
    if _agent_service_instance is None:
        if graphrag_service is None:
            from ..graphrag_service import get_service
            graphrag_service = get_service()
        _agent_service_instance = AgentService(graphrag_service)
    return _agent_service_instance
