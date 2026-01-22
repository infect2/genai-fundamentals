"""
GraphRAG MCP Server (HTTP/SSE Mode)

HTTP/SSE 기반 MCP 서버입니다.
URL을 통해 MCP 클라이언트와 통신합니다.

실행 방법:
    python -m genai-fundamentals.api.mcp_server_http

    # 또는 포트 지정
    python -m genai-fundamentals.api.mcp_server_http --port 3001

기본 URL: http://localhost:3001/sse

Claude Desktop 설정 (~/.claude/claude_desktop_config.json):
    {
      "mcpServers": {
        "graphrag": {
          "url": "http://localhost:3001/sse"
        }
      }
    }
"""

import argparse
import asyncio
import json
from typing import Any

from mcp.server import Server
from mcp.server.sse import SseServerTransport
from mcp.types import Tool, TextContent
from starlette.applications import Starlette
from starlette.routing import Route
from starlette.responses import JSONResponse
import uvicorn

from .service import get_service, GraphRAGService


# =============================================================================
# MCP 서버 초기화
# =============================================================================

mcp_server = Server("graphrag-mcp")

# GraphRAG 서비스 인스턴스 (지연 초기화)
_service: GraphRAGService | None = None


def get_graphrag_service() -> GraphRAGService:
    """GraphRAG 서비스 싱글톤 인스턴스 반환"""
    global _service
    if _service is None:
        _service = get_service()
    return _service


# =============================================================================
# MCP Tools 정의
# =============================================================================

TOOLS = [
    Tool(
        name="query",
        description=(
            "자연어로 Neo4j 그래프 데이터베이스를 쿼리합니다. "
            "영화, 배우, 감독, 장르 정보를 검색할 수 있습니다. "
            "예: 'Which actors appeared in The Matrix?', 'What movies did Tom Hanks star in?'"
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
                    "description": "세션 ID (대화 컨텍스트 유지용)",
                    "default": "default"
                },
                "reset_context": {
                    "type": "boolean",
                    "description": "쿼리 전 컨텍스트 초기화 여부",
                    "default": False
                }
            },
            "required": ["query"]
        }
    ),
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
    )
]


# =============================================================================
# MCP 핸들러
# =============================================================================

@mcp_server.list_tools()
async def list_tools() -> list[Tool]:
    """사용 가능한 MCP 도구 목록 반환"""
    return TOOLS


@mcp_server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """MCP 도구 호출 처리"""
    service = get_graphrag_service()

    if name == "query":
        query_text = arguments.get("query", "")
        session_id = arguments.get("session_id", "default")
        reset_context = arguments.get("reset_context", False)

        result = await service.query_async(
            query_text=query_text,
            session_id=session_id,
            reset_context=reset_context
        )

        response = {
            "answer": result.answer,
            "cypher": result.cypher,
            "context": result.context
        }

        return [TextContent(
            type="text",
            text=json.dumps(response, ensure_ascii=False, indent=2)
        )]

    elif name == "reset_session":
        session_id = arguments.get("session_id", "")
        success = service.reset_session(session_id)

        if success:
            message = f"Session '{session_id}' context has been reset"
        else:
            message = f"Session '{session_id}' not found"

        return [TextContent(type="text", text=message)]

    elif name == "list_sessions":
        sessions = service.list_sessions()

        response = {
            "sessions": sessions,
            "count": len(sessions)
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
# HTTP/SSE 서버 설정
# =============================================================================

# SSE Transport 인스턴스
sse_transport = SseServerTransport("/messages/")


async def handle_sse(request):
    """SSE 엔드포인트 핸들러"""
    async with sse_transport.connect_sse(
        request.scope, request.receive, request._send
    ) as streams:
        await mcp_server.run(
            streams[0],
            streams[1],
            mcp_server.create_initialization_options()
        )


async def handle_messages(request):
    """메시지 POST 엔드포인트 핸들러"""
    await sse_transport.handle_post_message(
        request.scope, request.receive, request._send
    )


async def handle_health(request):
    """헬스 체크 엔드포인트"""
    return JSONResponse({
        "status": "healthy",
        "server": "graphrag-mcp",
        "mode": "http/sse",
        "tools": [t.name for t in TOOLS]
    })


# Starlette 앱 생성
app = Starlette(
    debug=True,
    routes=[
        Route("/", handle_health),
        Route("/health", handle_health),
        Route("/sse", handle_sse),
        Route("/messages/", handle_messages, methods=["POST"]),
    ]
)


# =============================================================================
# 서버 실행
# =============================================================================

def main():
    """HTTP/SSE MCP 서버 실행"""
    import os

    parser = argparse.ArgumentParser(description="GraphRAG MCP Server (HTTP/SSE)")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=3001, help="Port to bind (default: 3001)")
    parser.add_argument("--ssl", action="store_true", help="Enable HTTPS with SSL")
    parser.add_argument("--ssl-cert", default=None, help="SSL certificate file path")
    parser.add_argument("--ssl-key", default=None, help="SSL key file path")
    args = parser.parse_args()

    # SSL 설정
    ssl_keyfile = None
    ssl_certfile = None
    protocol = "http"

    if args.ssl:
        # 기본 인증서 경로
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        ssl_certfile = args.ssl_cert or os.path.join(base_dir, "certs", "cert.pem")
        ssl_keyfile = args.ssl_key or os.path.join(base_dir, "certs", "key.pem")
        protocol = "https"

        if not os.path.exists(ssl_certfile) or not os.path.exists(ssl_keyfile):
            print(f"❌ SSL 인증서를 찾을 수 없습니다:")
            print(f"   cert: {ssl_certfile}")
            print(f"   key: {ssl_keyfile}")
            print(f"\n인증서 생성 방법:")
            print(f"   openssl req -x509 -newkey rsa:4096 -keyout certs/key.pem -out certs/cert.pem -days 365 -nodes -subj '/CN=localhost'")
            return

    print(f"🚀 GraphRAG MCP Server (HTTP/SSE) starting...")
    print(f"📡 SSE URL: {protocol}://localhost:{args.port}/sse")
    print(f"🔧 Tools: {[t.name for t in TOOLS]}")
    if args.ssl:
        print(f"🔒 SSL enabled")

    uvicorn.run(
        app,
        host=args.host,
        port=args.port,
        ssl_keyfile=ssl_keyfile,
        ssl_certfile=ssl_certfile
    )


if __name__ == "__main__":
    main()
