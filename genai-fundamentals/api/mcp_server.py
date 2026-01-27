"""
Capora AI Ontology Bot - MCP (Model Context Protocol) Server (Agent-Only)

MCP 프로토콜을 통해 지식 그래프 검색 기능을 제공하는 서버입니다.
모든 쿼리는 ReAct Agent를 통해 처리됩니다.

MCP Tools:
- agent_query: ReAct Agent를 사용한 자연어 쿼리 (v1 단일 에이전트)
- multi_agent_query: 멀티 에이전트 시스템으로 물류 도메인 쿼리 처리 (v2)
- list_agents: 등록된 도메인 에이전트 목록 조회
- reset_session: 세션 컨텍스트 초기화
- list_sessions: 활성 세션 목록 조회

실행 방법:
    python -m genai-fundamentals.api.mcp_server

Claude Desktop 설정 (~/.claude/claude_desktop_config.json):
    {
      "mcpServers": {
        "capora": {
          "command": "python",
          "args": ["-m", "genai-fundamentals.api.mcp_server"],
          "cwd": "/path/to/genai-fundamentals"
        }
      }
    }
"""

import asyncio
import json
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from .graphrag_service import get_service, GraphRAGService
from .agent import AgentService
from .multi_agents.orchestrator import OrchestratorService, get_orchestrator
from .multi_agents.registry import get_registry


# =============================================================================
# MCP 서버 초기화
# =============================================================================

app = Server("capora-mcp")

# Ontology 서비스 인스턴스 (지연 초기화)
_service: GraphRAGService | None = None
_agent_service: AgentService | None = None
_orchestrator: OrchestratorService | None = None


def get_graphrag_service() -> GraphRAGService:
    """GraphRAG 서비스 싱글톤 인스턴스 반환"""
    global _service
    if _service is None:
        _service = get_service()
    return _service


def get_agent_service() -> AgentService:
    """AgentService 싱글톤 인스턴스 반환"""
    global _agent_service
    if _agent_service is None:
        _agent_service = AgentService(get_graphrag_service())
    return _agent_service


def get_orchestrator_service() -> OrchestratorService:
    """OrchestratorService 싱글톤 인스턴스 반환"""
    global _orchestrator
    if _orchestrator is None:
        registry = get_registry()
        _orchestrator = get_orchestrator(registry, get_graphrag_service())
    return _orchestrator


# =============================================================================
# MCP Tools 정의
# =============================================================================

TOOLS = [
    Tool(
        name="reset_session",
        description="특정 세션의 대화 히스토리를 초기화합니다.",
        inputSchema={
            "type": "object",
            "properties": {
                "session_id": {
                    "type": "string",
                    "description": "초기화할 세션 ID"
                }
            },
            "required": ["session_id"]
        }
    ),
    Tool(
        name="list_sessions",
        description="현재 활성화된 모든 세션 ID 목록을 조회합니다.",
        inputSchema={
            "type": "object",
            "properties": {}
        }
    ),
    Tool(
        name="multi_agent_query",
        description=(
            "멀티 에이전트 시스템으로 물류 도메인 쿼리를 처리합니다. "
            "WMS(창고), TMS(운송), FMS(차량), TAP(호출) 도메인을 자동 라우팅하며, "
            "크로스 도메인 쿼리도 지원합니다."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "자연어 질문"
                },
                "session_id": {
                    "type": "string",
                    "description": "세션 ID",
                    "default": "default"
                },
                "preferred_domain": {
                    "type": "string",
                    "enum": ["auto", "wms", "tms", "fms", "tap", "memory"],
                    "description": "선호 도메인 (auto=자동 라우팅)",
                    "default": "auto"
                },
                "allow_cross_domain": {
                    "type": "boolean",
                    "description": "크로스 도메인 쿼리 허용",
                    "default": True
                }
            },
            "required": ["query"]
        }
    ),
    Tool(
        name="list_agents",
        description="등록된 도메인 에이전트 목록을 조회합니다.",
        inputSchema={
            "type": "object",
            "properties": {}
        }
    ),
    Tool(
        name="agent_query",
        description=(
            "자연어로 Neo4j 지식 그래프를 쿼리합니다. "
            "ReAct Agent가 multi-step reasoning을 통해 여러 도구를 조합하여 답변을 생성합니다. "
            "예: 'X와 연결된 엔티티는?', '특정 관계 유형을 가진 노드 찾기'"
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "복잡한 자연어 질문"
                },
                "session_id": {
                    "type": "string",
                    "description": "세션 ID (대화 컨텍스트 유지용)",
                    "default": "default"
                }
            },
            "required": ["query"]
        }
    )
]


# =============================================================================
# MCP 핸들러
# =============================================================================

@app.list_tools()
async def list_tools() -> list[Tool]:
    """사용 가능한 MCP 도구 목록 반환"""
    return TOOLS


@app.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """
    MCP 도구 호출 처리

    Args:
        name: 도구 이름
        arguments: 도구 인자

    Returns:
        TextContent 리스트 형식의 응답
    """
    service = get_graphrag_service()

    if name == "reset_session":
        # 세션 초기화
        session_id = arguments.get("session_id", "")
        success = service.reset_session(session_id)

        if success:
            message = f"Session '{session_id}' context has been reset"
        else:
            message = f"Session '{session_id}' not found"

        return [TextContent(type="text", text=message)]

    elif name == "list_sessions":
        # 세션 목록 조회
        sessions = service.list_sessions()

        response = {
            "sessions": sessions,
            "count": len(sessions)
        }

        return [TextContent(
            type="text",
            text=json.dumps(response, ensure_ascii=False, indent=2)
        )]

    elif name == "agent_query":
        # Agent를 사용한 복잡한 쿼리 실행
        query_text = arguments.get("query", "")
        session_id = arguments.get("session_id", "default")

        agent = get_agent_service()
        result = await agent.query_async(
            query_text=query_text,
            session_id=session_id
        )

        # 응답 포맷팅
        response = {
            "answer": result.answer,
            "thoughts": result.thoughts,
            "tool_calls": result.tool_calls,
            "tool_results": result.tool_results,
            "iterations": result.iterations
        }
        if result.token_usage:
            response["token_usage"] = {
                "total_tokens": result.token_usage.total_tokens,
                "prompt_tokens": result.token_usage.prompt_tokens,
                "completion_tokens": result.token_usage.completion_tokens,
                "total_cost": result.token_usage.total_cost
            }

        return [TextContent(
            type="text",
            text=json.dumps(response, ensure_ascii=False, indent=2)
        )]

    elif name == "multi_agent_query":
        # 멀티 에이전트 쿼리 실행
        query_text = arguments.get("query", "")
        session_id = arguments.get("session_id", "default")
        preferred_domain = arguments.get("preferred_domain", "auto")
        allow_cross_domain = arguments.get("allow_cross_domain", True)

        orchestrator = get_orchestrator_service()
        result = await orchestrator.query_async(
            query_text=query_text,
            session_id=session_id,
            preferred_domain=preferred_domain,
            allow_cross_domain=allow_cross_domain
        )

        response = {
            "answer": result.answer,
            "domain_decision": result.domain_decision,
            "agent_results": result.agent_results
        }
        if result.token_usage:
            response["token_usage"] = {
                "total_tokens": result.token_usage.total_tokens,
                "prompt_tokens": result.token_usage.prompt_tokens,
                "completion_tokens": result.token_usage.completion_tokens,
                "total_cost": result.token_usage.total_cost
            }

        return [TextContent(
            type="text",
            text=json.dumps(response, ensure_ascii=False, indent=2)
        )]

    elif name == "list_agents":
        # 등록된 도메인 에이전트 목록 조회
        registry = get_registry()
        agents_info = registry.get_agent_info()

        response = {
            "agents": agents_info,
            "count": len(agents_info)
        }

        return [TextContent(
            type="text",
            text=json.dumps(response, ensure_ascii=False, indent=2)
        )]

    else:
        return [TextContent(
            type="text",
            text=f"Unknown tool: {name}"
        )]


# =============================================================================
# 서버 실행
# =============================================================================

async def main():
    """MCP 서버 메인 함수 (stdio 모드)"""
    async with stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options()
        )


if __name__ == "__main__":
    asyncio.run(main())
