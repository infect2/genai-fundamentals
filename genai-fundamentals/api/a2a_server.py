"""
Capora AI Ontology Bot - A2A (Agent2Agent) Protocol Server (Agent-Only)

A2A 프로토콜을 통해 지식 그래프 검색 기능을 에이전트 간 통신으로 제공합니다.
모든 쿼리는 ReAct Agent를 통해 처리됩니다.

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
    version="1.0.0",
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

    def _get_service(self) -> GraphRAGService:
        if self._service is None:
            self._service = get_service()
        return self._service

    def _get_agent_service(self) -> AgentService:
        if self._agent_service is None:
            self._agent_service = AgentService(self._get_service())
        return self._agent_service

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        """A2A 요청 처리 - 모든 쿼리는 ReAct Agent를 통해 처리"""
        # 사용자 메시지에서 텍스트 추출
        query = self._extract_text(context.message)
        if not query:
            await self._send_error(context, event_queue, "메시지에서 텍스트를 추출할 수 없습니다.")
            return

        try:
            session_id = context.context_id or "a2a-default"

            agent = self._get_agent_service()
            result = await agent.query_async(
                query_text=query, session_id=session_id
            )

            # Agent 응답: 텍스트 + 구조화 데이터
            data = {
                "thoughts": result.thoughts,
                "tool_calls": result.tool_calls,
                "iterations": result.iterations,
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

            # 응답 메시지 전송
            response = new_agent_parts_message(
                parts=parts,
                context_id=context.context_id,
                task_id=context.task_id,
            )
            await event_queue.enqueue_event(response)

            # 완료 상태 업데이트
            await event_queue.enqueue_event(
                TaskStatusUpdateEvent(
                    task_id=context.task_id,
                    context_id=context.context_id or "",
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
