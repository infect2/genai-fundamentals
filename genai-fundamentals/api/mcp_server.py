"""
GraphRAG MCP (Model Context Protocol) Server (Agent-Only)

MCP 프로토콜을 통해 GraphRAG 기능을 제공하는 서버입니다.
모든 쿼리는 ReAct Agent를 통해 처리됩니다.

MCP Tools:
- agent_query: ReAct Agent를 사용한 자연어 쿼리
- reset_session: 세션 컨텍스트 초기화
- list_sessions: 활성 세션 목록 조회

실행 방법:
    python -m genai-fundamentals.api.mcp_server

Claude Desktop 설정 (~/.claude/claude_desktop_config.json):
    {
      "mcpServers": {
        "graphrag": {
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


# =============================================================================
# MCP 서버 초기화
# =============================================================================

app = Server("graphrag-mcp")

# GraphRAG 서비스 인스턴스 (지연 초기화)
_service: GraphRAGService | None = None
_agent_service: AgentService | None = None


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
        name="agent_query",
        description=(
            "자연어로 Neo4j 그래프 데이터베이스를 쿼리합니다. "
            "ReAct Agent가 multi-step reasoning을 통해 여러 도구를 조합하여 답변을 생성합니다. "
            "예: 'Which actors appeared in The Matrix?', 'Tom Hanks와 비슷한 배우가 출연한 SF 영화는?'"
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
