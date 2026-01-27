"""
Orchestrator Service Module

Master Orchestrator 서비스 클래스입니다.
도메인 라우팅, 에이전트 실행, 결과 통합을 조율합니다.

Usage:
    from genai_fundamentals.api.multi_agents.orchestrator import OrchestratorService

    orchestrator = OrchestratorService(registry, graphrag_service)
    result = await orchestrator.query_async("배송 현황 알려줘")
"""

import json
import logging
import asyncio
from dataclasses import dataclass, field, asdict
from typing import Optional, List, Dict, Any, AsyncGenerator

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

from ..base import DomainType, DomainRouteDecision, DomainAgentResult
from ..registry import AgentRegistry, get_registry
from .router import DomainRouter
from .prompts import RESPONSE_SYNTHESIS_PROMPT
from ...models import TokenUsage
from ...config import get_config

logger = logging.getLogger(__name__)


@dataclass
class MultiAgentResult:
    """
    멀티 에이전트 실행 결과

    Attributes:
        answer: 통합된 최종 답변
        domain_decision: 도메인 라우팅 결정
        agent_results: 도메인별 실행 결과
        token_usage: 총 토큰 사용량
    """
    answer: str
    domain_decision: Dict[str, Any]
    agent_results: Dict[str, Dict[str, Any]]
    token_usage: Optional[TokenUsage] = None


class OrchestratorService:
    """
    Master Orchestrator 서비스

    사용자 쿼리를 분석하여 적합한 도메인 에이전트로 라우팅하고,
    단일/크로스 도메인 쿼리를 처리합니다.

    Architecture:
        1. 의도 분석 (Domain Router)
        2. 실행 계획 수립 (크로스 도메인 시)
        3. 도메인 에이전트 실행
        4. 결과 통합

    Example:
        orchestrator = OrchestratorService(registry, graphrag_service)
        result = await orchestrator.query_async("배송 현황 알려줘")
        print(result.answer)
    """

    def __init__(
        self,
        registry: Optional[AgentRegistry] = None,
        graphrag_service=None,
        model_name: Optional[str] = None,
        enable_cross_domain: bool = True
    ):
        """
        OrchestratorService 초기화

        Args:
            registry: AgentRegistry 인스턴스 (None이면 싱글톤 사용)
            graphrag_service: GraphRAGService 인스턴스
            model_name: LLM 모델명
            enable_cross_domain: 크로스 도메인 처리 활성화 여부
        """
        self._registry = registry or get_registry()
        self._graphrag_service = graphrag_service
        self._model_name = model_name
        self._enable_cross_domain = enable_cross_domain

        config = get_config()
        self._max_cross_domain_agents = config.multi_agent.max_cross_domain_agents
        self._routing_threshold = config.multi_agent.routing_confidence_threshold

        # LLM 및 Router 초기화
        from ....tools.llm_provider import create_langchain_llm, get_router_model_name

        router_llm = create_langchain_llm(
            model_name=get_router_model_name(),
            temperature=0
        )
        self._router = DomainRouter(llm=router_llm, use_llm_routing=True)

        # 결과 통합용 LLM
        self._llm = create_langchain_llm(model_name=model_name, temperature=0)
        self._synthesis_prompt = ChatPromptTemplate.from_template(RESPONSE_SYNTHESIS_PROMPT)
        self._synthesis_chain = self._synthesis_prompt | self._llm | StrOutputParser()

    def query(
        self,
        query_text: str,
        session_id: str = "default",
        preferred_domain: str = "auto",
        allow_cross_domain: bool = True
    ) -> MultiAgentResult:
        """
        쿼리 실행 (동기)

        Args:
            query_text: 사용자 쿼리
            session_id: 세션 ID
            preferred_domain: 선호 도메인 ("auto"면 자동 라우팅)
            allow_cross_domain: 크로스 도메인 허용 여부

        Returns:
            MultiAgentResult 객체
        """
        from ....tools.llm_provider import get_token_tracker

        with get_token_tracker() as cb:
            # 1. 도메인 라우팅
            force_domain = None if preferred_domain == "auto" else preferred_domain
            decision = self._router.route(query_text, force_domain=force_domain)

            # 2. 에이전트 실행
            agent_results = {}

            # 주요 도메인 에이전트 실행
            primary_result = self._execute_domain_agent(
                decision.domain, query_text, session_id
            )
            if primary_result:
                agent_results[decision.domain.value] = asdict(primary_result)

            # 크로스 도메인 처리
            if (
                allow_cross_domain
                and self._enable_cross_domain
                and decision.requires_cross_domain
                and decision.secondary_domains
            ):
                for secondary_domain in decision.secondary_domains[:self._max_cross_domain_agents - 1]:
                    secondary_result = self._execute_domain_agent(
                        secondary_domain, query_text, session_id,
                        context={"primary_result": primary_result.answer if primary_result else ""}
                    )
                    if secondary_result:
                        agent_results[secondary_domain.value] = asdict(secondary_result)

            # 3. 결과 통합
            final_answer = self._synthesize_results(query_text, agent_results)

        # 대화 이력 저장 (Neo4j + 캐시)
        try:
            self._graphrag_service._add_to_history(session_id, query_text, final_answer)
        except Exception as e:
            logger.warning(f"Failed to save history for session {session_id}: {e}")

        return MultiAgentResult(
            answer=final_answer,
            domain_decision={
                "primary": decision.domain.value,
                "secondary": [d.value for d in decision.secondary_domains],
                "confidence": decision.confidence,
                "reasoning": decision.reasoning,
                "cross_domain": decision.requires_cross_domain
            },
            agent_results=agent_results,
            token_usage=TokenUsage(
                total_tokens=cb.total_tokens,
                prompt_tokens=cb.prompt_tokens,
                completion_tokens=cb.completion_tokens,
                total_cost=cb.total_cost
            )
        )

    async def query_async(
        self,
        query_text: str,
        session_id: str = "default",
        preferred_domain: str = "auto",
        allow_cross_domain: bool = True
    ) -> MultiAgentResult:
        """
        쿼리 실행 (비동기)

        Args:
            query_text: 사용자 쿼리
            session_id: 세션 ID
            preferred_domain: 선호 도메인
            allow_cross_domain: 크로스 도메인 허용 여부

        Returns:
            MultiAgentResult 객체
        """
        from ....tools.llm_provider import get_token_tracker

        with get_token_tracker() as cb:
            # 1. 도메인 라우팅 (비동기)
            force_domain = None if preferred_domain == "auto" else preferred_domain
            decision = await self._router.route_async(query_text, force_domain=force_domain)

            # 2. 에이전트 실행
            agent_results = {}

            # 주요 도메인 에이전트 실행
            primary_result = await self._execute_domain_agent_async(
                decision.domain, query_text, session_id
            )
            if primary_result:
                agent_results[decision.domain.value] = asdict(primary_result)

            # 크로스 도메인 처리 (병렬 실행)
            if (
                allow_cross_domain
                and self._enable_cross_domain
                and decision.requires_cross_domain
                and decision.secondary_domains
            ):
                tasks = []
                for secondary_domain in decision.secondary_domains[:self._max_cross_domain_agents - 1]:
                    task = self._execute_domain_agent_async(
                        secondary_domain, query_text, session_id,
                        context={"primary_result": primary_result.answer if primary_result else ""}
                    )
                    tasks.append((secondary_domain, task))

                for secondary_domain, task in tasks:
                    try:
                        secondary_result = await task
                        if secondary_result:
                            agent_results[secondary_domain.value] = asdict(secondary_result)
                    except Exception as e:
                        logger.error(f"Secondary agent {secondary_domain.value} failed: {e}")

            # 3. 결과 통합
            final_answer = await self._synthesize_results_async(query_text, agent_results)

        # 대화 이력 저장 (Neo4j + 캐시)
        try:
            self._graphrag_service._add_to_history(session_id, query_text, final_answer)
        except Exception as e:
            logger.warning(f"Failed to save history for session {session_id}: {e}")

        return MultiAgentResult(
            answer=final_answer,
            domain_decision={
                "primary": decision.domain.value,
                "secondary": [d.value for d in decision.secondary_domains],
                "confidence": decision.confidence,
                "reasoning": decision.reasoning,
                "cross_domain": decision.requires_cross_domain
            },
            agent_results=agent_results,
            token_usage=TokenUsage(
                total_tokens=cb.total_tokens,
                prompt_tokens=cb.prompt_tokens,
                completion_tokens=cb.completion_tokens,
                total_cost=cb.total_cost
            )
        )

    def _execute_domain_agent(
        self,
        domain: DomainType,
        query_text: str,
        session_id: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Optional[DomainAgentResult]:
        """도메인 에이전트 실행 (동기)"""
        agent = self._registry.get(domain)
        if not agent:
            logger.warning(f"Agent not found for domain: {domain.value}")
            return None

        try:
            return agent.query(query_text, session_id, context)
        except Exception as e:
            logger.error(f"Agent {domain.value} execution failed: {e}")
            return DomainAgentResult(
                answer=f"에이전트 실행 오류: {str(e)}",
                domain=domain,
                metadata={"error": str(e)}
            )

    async def _execute_domain_agent_async(
        self,
        domain: DomainType,
        query_text: str,
        session_id: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Optional[DomainAgentResult]:
        """도메인 에이전트 실행 (비동기)"""
        agent = self._registry.get(domain)
        if not agent:
            logger.warning(f"Agent not found for domain: {domain.value}")
            return None

        try:
            return await agent.query_async(query_text, session_id, context)
        except Exception as e:
            logger.error(f"Agent {domain.value} async execution failed: {e}")
            return DomainAgentResult(
                answer=f"에이전트 실행 오류: {str(e)}",
                domain=domain,
                metadata={"error": str(e)}
            )

    def _synthesize_results(
        self,
        query: str,
        agent_results: Dict[str, Dict[str, Any]]
    ) -> str:
        """결과 통합 (동기)"""
        if not agent_results:
            return "요청을 처리할 수 있는 에이전트가 없습니다."

        # 단일 에이전트 결과면 그대로 반환
        if len(agent_results) == 1:
            return list(agent_results.values())[0].get("answer", "")

        # 다중 에이전트 결과 통합
        results_text = ""
        for domain, result in agent_results.items():
            results_text += f"\n### {domain.upper()} 결과\n{result.get('answer', '')}\n"

        try:
            return self._synthesis_chain.invoke({
                "query": query,
                "agent_results": results_text
            })
        except Exception as e:
            logger.error(f"Result synthesis failed: {e}")
            return results_text  # 통합 실패 시 원본 반환

    async def _synthesize_results_async(
        self,
        query: str,
        agent_results: Dict[str, Dict[str, Any]]
    ) -> str:
        """결과 통합 (비동기)"""
        if not agent_results:
            return "요청을 처리할 수 있는 에이전트가 없습니다."

        if len(agent_results) == 1:
            return list(agent_results.values())[0].get("answer", "")

        results_text = ""
        for domain, result in agent_results.items():
            results_text += f"\n### {domain.upper()} 결과\n{result.get('answer', '')}\n"

        try:
            return await self._synthesis_chain.ainvoke({
                "query": query,
                "agent_results": results_text
            })
        except Exception as e:
            logger.error(f"Async result synthesis failed: {e}")
            return results_text

    async def query_stream(
        self,
        query_text: str,
        session_id: str = "default",
        preferred_domain: str = "auto",
        allow_cross_domain: bool = True
    ) -> AsyncGenerator[str, None]:
        """
        멀티 에이전트 쿼리 스트리밍

        SSE 형식으로 도메인 라우팅 정보와 에이전트 응답을 스트리밍합니다.

        이벤트 순서:
        1. domain_decision: 도메인 라우팅 결과
        2. token/tool_call/tool_result: 에이전트 실행 스트리밍
        3. done: 완료 (agent_results, token_usage)

        Args:
            query_text: 사용자 쿼리
            session_id: 세션 ID
            preferred_domain: 선호 도메인
            allow_cross_domain: 크로스 도메인 허용 여부

        Yields:
            SSE 형식 문자열
        """
        from ....tools.llm_provider import get_token_tracker

        # 1. 도메인 라우팅
        force_domain = None if preferred_domain == "auto" else preferred_domain
        decision = await self._router.route_async(query_text, force_domain=force_domain)

        # 도메인 라우팅 결과를 먼저 전송
        domain_decision = {
            "primary": decision.domain.value,
            "secondary": [d.value for d in decision.secondary_domains],
            "confidence": decision.confidence,
            "reasoning": decision.reasoning,
            "cross_domain": decision.requires_cross_domain
        }
        yield f"data: {json.dumps({'type': 'domain_decision', 'decision': domain_decision})}\n\n"

        # 2. 주요 도메인 에이전트 스트리밍 실행
        agent = self._registry.get(decision.domain)
        if not agent:
            yield f"data: {json.dumps({'type': 'error', 'message': f'Agent not found for domain: {decision.domain.value}'})}\n\n"
            return

        agent_results = {}
        done_data_from_agent = None

        try:
            async for chunk in agent.query_stream(query_text, session_id):
                # 도메인 에이전트의 done 이벤트를 가로채서 agent_results에 저장
                if chunk.startswith("data: "):
                    try:
                        data = json.loads(chunk[6:].strip())
                        if data.get("type") == "done":
                            # done 이벤트를 저장하고, token/tool_call/tool_result만 통과시킴
                            done_data_from_agent = data
                            agent_results[decision.domain.value] = {
                                "answer": data.get("final_answer", ""),
                                "domain": data.get("domain", decision.domain.value),
                                "tool_calls": data.get("tool_calls", []),
                                "tool_results": data.get("tool_results", []),
                                "token_usage": data.get("token_usage", {})
                            }
                            continue  # done은 마지막에 통합해서 보냄
                    except json.JSONDecodeError:
                        pass
                yield chunk
        except Exception as e:
            logger.error(f"Stream agent {decision.domain.value} failed: {e}")
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

        # 3. 크로스 도메인 처리 (스트리밍에서는 순차 실행)
        if (
            allow_cross_domain
            and self._enable_cross_domain
            and decision.requires_cross_domain
            and decision.secondary_domains
        ):
            primary_answer = ""
            if done_data_from_agent:
                primary_answer = done_data_from_agent.get("final_answer", "")

            for secondary_domain in decision.secondary_domains[:self._max_cross_domain_agents - 1]:
                yield f"data: {json.dumps({'type': 'cross_domain', 'domain': secondary_domain.value})}\n\n"
                try:
                    secondary_result = await self._execute_domain_agent_async(
                        secondary_domain, query_text, session_id,
                        context={"primary_result": primary_answer}
                    )
                    if secondary_result:
                        agent_results[secondary_domain.value] = asdict(secondary_result)
                except Exception as e:
                    logger.error(f"Secondary agent {secondary_domain.value} failed: {e}")

        # 4. 최종 완료 이벤트
        # 토큰 사용량 합산
        total_tokens = 0
        prompt_tokens = 0
        completion_tokens = 0
        total_cost = 0.0
        for ar in agent_results.values():
            tu = ar.get("token_usage", {})
            if isinstance(tu, dict):
                total_tokens += tu.get("total_tokens", 0)
                prompt_tokens += tu.get("prompt_tokens", 0)
                completion_tokens += tu.get("completion_tokens", 0)
                total_cost += tu.get("total_cost", 0.0)

        final_answer = ""
        if done_data_from_agent:
            final_answer = done_data_from_agent.get("final_answer", "")

        done_event = {
            "type": "done",
            "final_answer": final_answer,
            "domain_decision": domain_decision,
            "agent_results": agent_results,
            "token_usage": {
                "total_tokens": total_tokens,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_cost": total_cost
            }
        }
        yield f"data: {json.dumps(done_event, default=str)}\n\n"

        # 대화 이력 저장 (Neo4j + 캐시)
        try:
            self._graphrag_service._add_to_history(session_id, query_text, final_answer)
        except Exception as e:
            logger.warning(f"Failed to save history for session {session_id}: {e}")

    def get_available_domains(self) -> List[str]:
        """등록된 도메인 목록 반환"""
        return [d.value for d in self._registry.list_domains()]

    def get_agent_info(self) -> List[dict]:
        """등록된 에이전트 정보 반환"""
        return self._registry.get_agent_info()


# =============================================================================
# 싱글톤 인스턴스
# =============================================================================

_orchestrator_instance: Optional[OrchestratorService] = None


def get_orchestrator(
    registry: Optional[AgentRegistry] = None,
    graphrag_service=None
) -> OrchestratorService:
    """
    OrchestratorService 싱글톤 인스턴스 반환

    Args:
        registry: AgentRegistry 인스턴스
        graphrag_service: GraphRAGService 인스턴스

    Returns:
        OrchestratorService 인스턴스
    """
    global _orchestrator_instance
    if _orchestrator_instance is None:
        _orchestrator_instance = OrchestratorService(registry, graphrag_service)
    return _orchestrator_instance


def reset_orchestrator() -> None:
    """Orchestrator 리셋 (테스트용)"""
    global _orchestrator_instance
    _orchestrator_instance = None
