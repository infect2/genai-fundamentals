"""
Capora AI Ontology Bot - A2A (Agent2Agent) Protocol Server (Agent-Only + Multi-Agent v2)

A2A 프로토콜을 통해 지식 그래프 검색 기능을 에이전트 간 통신으로 제공합니다.
v1: 단일 ReAct Agent를 통한 쿼리 처리
v2: 멀티 에이전트 시스템을 통한 도메인별 쿼리 처리

실행 방법:
    python -m genai-fundamentals.api.a2a_server
    python -m genai-fundamentals.api.a2a_server --port 9000

기본 URL: http://localhost:9000
AgentCard: http://localhost:9000/.well-known/agent.json
"""

import argparse
import asyncio
import uuid

from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import (
    AgentCard,
    AgentSkill,
    AgentCapabilities,
    Part,
    TextPart,
    DataPart,
    TaskStatusUpdateEvent,
    TaskArtifactUpdateEvent,
    TaskState,
    TaskStatus,
    Artifact,
)
from a2a.utils import new_agent_text_message, new_agent_parts_message
import uvicorn

from .graphrag_service import get_service, GraphRAGService
from .agent.service import AgentService
from .multi_agents.orchestrator import OrchestratorService, get_orchestrator
from .multi_agents.registry import get_registry


# =============================================================================
# AgentCard 정의
# =============================================================================

AGENT_CARD = AgentCard(
    name="Capora AI Ontology Bot",
    description=(
        "Neo4j 그래프 데이터베이스 기반 지식 그래프 에이전트. "
        "온톨로지 기반 데이터를 자연어로 검색합니다. "
        "ReAct Agent가 multi-step reasoning을 통해 답변을 생성합니다."
    ),
    version="2.0.0",
    url="http://localhost:9000",
    default_input_modes=["text/plain", "application/json"],
    default_output_modes=["text/plain", "application/json"],
    capabilities=AgentCapabilities(
        streaming=False,
        push_notifications=False,
    ),
    skills=[
        AgentSkill(
            id="ontology_agent",
            name="Capora AI ReAct Agent",
            description=(
                "자연어로 Neo4j 지식 그래프를 쿼리합니다. "
                "Multi-step reasoning을 통해 여러 도구를 조합하여 답변을 생성합니다."
            ),
            tags=["ontology", "neo4j", "knowledge-graph", "agent", "react"],
            examples=[
                "What entities are connected to X?",
                "Find all relationships of type Y",
                "X와 관련된 데이터를 찾아줘",
                "가장 많은 관계를 가진 노드는?",
            ],
            input_modes=["text/plain"],
            output_modes=["text/plain", "application/json"],
        ),
        AgentSkill(
            id="multi_agent_query",
            name="Multi-Agent Domain Query",
            description=(
                "멀티 에이전트 시스템을 통해 물류 도메인별 쿼리를 처리합니다. "
                "WMS, TMS, FMS, TAP!, Memory 도메인 에이전트가 협력하여 답변을 생성합니다."
            ),
            tags=["multi-agent", "wms", "tms", "fms", "tap", "memory", "logistics"],
            examples=[
                "배송 현황 알려줘",
                "창고 적재율 조회해줘",
                "정비 중인 차량 목록",
                "내 차번호 기억해줘",
            ],
            input_modes=["text/plain", "application/json"],
            output_modes=["text/plain", "application/json"],
        ),
    ],
)


# =============================================================================
# AgentExecutor 구현
# =============================================================================

class CaporaAgentExecutor(AgentExecutor):
    """Capora AI 비즈니스 로직을 A2A 프로토콜에 연결하는 실행기"""

    def __init__(self):
        self._service: GraphRAGService | None = None
        self._agent_service: AgentService | None = None
        self._orchestrator_service: OrchestratorService | None = None

    def _get_service(self) -> GraphRAGService:
        if self._service is None:
            self._service = get_service()
        return self._service

    def _get_agent_service(self) -> AgentService:
        if self._agent_service is None:
            self._agent_service = AgentService(self._get_service())
        return self._agent_service

    def _get_orchestrator_service(self) -> OrchestratorService:
        if self._orchestrator_service is None:
            self._initialize_multi_agent()
            registry = get_registry()
            self._orchestrator_service = get_orchestrator(registry, self._get_service())
        return self._orchestrator_service

    def _initialize_multi_agent(self) -> None:
        """멀티 에이전트 시스템 초기화 - 도메인 에이전트들을 레지스트리에 등록"""
        import logging
        logger = logging.getLogger(__name__)
        registry = get_registry()
        svc = self._get_service()

        for module_path, class_name, label in [
            (".multi_agents.tms", "TMSAgent", "TMS"),
            (".multi_agents.wms", "WMSAgent", "WMS"),
            (".multi_agents.fms", "FMSAgent", "FMS"),
            (".multi_agents.tap", "TAPAgent", "TAP"),
            (".multi_agents.memory", "MemoryAgent", "Memory"),
        ]:
            try:
                mod = __import__(f"genai-fundamentals.api{module_path}", fromlist=[class_name])
                agent_cls = getattr(mod, class_name)
                agent = agent_cls(graphrag_service=svc)
                registry.register(agent)
            except Exception as e:
                logger.warning(f"Failed to register {label} agent: {e}")

    def _extract_data(self, message) -> dict | None:
        """메시지에서 DataPart 추출"""
        if message and message.parts:
            for part in message.parts:
                if hasattr(part.root, "data"):
                    return part.root.data
        return None

    def _is_multi_agent_request(self, message) -> bool:
        """v2 멀티 에이전트 요청인지 판별"""
        data = self._extract_data(message)
        if data and isinstance(data, dict):
            return "skill" in data and data["skill"] == "multi_agent_query" or "preferred_domain" in data
        return False

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        """A2A 요청 처리 - 모든 쿼리는 ReAct Agent를 통해 처리"""
        # 사용자 메시지에서 텍스트 추출
        query = self._extract_text(context.message)
        if not query:
            await self._send_error(context, event_queue, "메시지에서 텍스트를 추출할 수 없습니다.")
            return

        try:
            # Multi-turn 지원: context_id가 없으면 새로 생성하여 세션 유지
            effective_context_id = context.context_id or f"a2a-session-{uuid.uuid4().hex[:8]}"
            session_id = effective_context_id

            if self._is_multi_agent_request(context.message):
                # v2: 멀티 에이전트 처리
                req_data = self._extract_data(context.message) or {}
                preferred_domain = req_data.get("preferred_domain", "auto")
                allow_cross_domain = req_data.get("allow_cross_domain", True)
                if "session_id" in req_data:
                    session_id = req_data["session_id"]

                orchestrator = self._get_orchestrator_service()
                result = await orchestrator.query_async(
                    query_text=query,
                    session_id=session_id,
                    preferred_domain=preferred_domain,
                    allow_cross_domain=allow_cross_domain,
                )

                data = {
                    "domain_decision": result.domain_decision,
                    "agent_results": result.agent_results,
                    "session_id": session_id,
                }
                if result.token_usage:
                    data["token_usage"] = {
                        "total_tokens": result.token_usage.total_tokens,
                        "prompt_tokens": result.token_usage.prompt_tokens,
                        "completion_tokens": result.token_usage.completion_tokens,
                        "total_cost": result.token_usage.total_cost,
                    }
            else:
                # v1: 단일 에이전트 처리
                agent = self._get_agent_service()
                result = await agent.query_async(
                    query_text=query, session_id=session_id
                )

                data = {
                    "thoughts": result.thoughts,
                    "tool_calls": result.tool_calls,
                    "iterations": result.iterations,
                    "session_id": session_id,
                }
                if result.token_usage:
                    data["token_usage"] = {
                        "total_tokens": result.token_usage.total_tokens,
                        "prompt_tokens": result.token_usage.prompt_tokens,
                        "completion_tokens": result.token_usage.completion_tokens,
                        "total_cost": result.token_usage.total_cost,
                    }

            parts = [
                Part(root=TextPart(text=result.answer)),
                Part(root=DataPart(data=data)),
            ]

            response = new_agent_parts_message(
                parts=parts,
                context_id=effective_context_id,
                task_id=context.task_id,
            )
            await event_queue.enqueue_event(response)

            await event_queue.enqueue_event(
                TaskStatusUpdateEvent(
                    task_id=context.task_id,
                    context_id=effective_context_id,
                    final=True,
                    status=TaskStatus(state=TaskState.completed),
                )
            )

        except Exception as e:
            await self._send_error(context, event_queue, str(e))

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        """태스크 취소 처리"""
        await event_queue.enqueue_event(
            TaskStatusUpdateEvent(
                task_id=context.task_id,
                context_id=context.context_id or "",
                final=True,
                status=TaskStatus(state=TaskState.canceled),
            )
        )

    def _extract_text(self, message) -> str:
        """메시지에서 텍스트 추출"""
        texts = []
        if message and message.parts:
            for part in message.parts:
                if hasattr(part.root, "text"):
                    texts.append(part.root.text)
        return " ".join(texts)

    async def _send_error(
        self, context: RequestContext, event_queue: EventQueue, error_msg: str
    ) -> None:
        """에러 응답 전송"""
        error_message = new_agent_text_message(
            f"Error: {error_msg}",
            context_id=context.context_id,
            task_id=context.task_id,
        )
        await event_queue.enqueue_event(error_message)
        await event_queue.enqueue_event(
            TaskStatusUpdateEvent(
                task_id=context.task_id,
                context_id=context.context_id or "",
                final=True,
                status=TaskStatus(state=TaskState.failed),
            )
        )


# =============================================================================
# 서버 실행
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description="Capora AI A2A Server")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=9000)
    args = parser.parse_args()

    # AgentCard URL 업데이트
    agent_card = AGENT_CARD.model_copy()
    agent_card.url = f"http://{args.host}:{args.port}"

    # A2A 서버 구성
    executor = CaporaAgentExecutor()
    request_handler = DefaultRequestHandler(
        agent_executor=executor,
        task_store=InMemoryTaskStore(),
    )
    a2a_app = A2AStarletteApplication(
        agent_card=agent_card,
        http_handler=request_handler,
    )

    print(f"Capora AI A2A Server starting...")
    print(f"URL: http://localhost:{args.port}")
    print(f"AgentCard: http://localhost:{args.port}/.well-known/agent.json")
    print(f"Skills: {[s.id for s in AGENT_CARD.skills]}")

    uvicorn.run(a2a_app.build(), host=args.host, port=args.port)


if __name__ == "__main__":
    main()
