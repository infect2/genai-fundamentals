"""
GraphRAG REST API Server

FastAPI 기반의 REST API 서버입니다.
GraphRAG 비즈니스 로직은 graph_rag_service 모듈에 위임합니다.

엔드포인트:
- GET  /           : 서버 상태 확인
- POST /query      : 자연어 쿼리 실행 (스트리밍/비스트리밍)
- POST /reset/{id} : 세션 컨텍스트 리셋
- GET  /sessions   : 활성 세션 목록

실행 방법:
    python -m genai-fundamentals.api.server
    또는
    uvicorn genai-fundamentals.api.server:app --reload
"""

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional

# GraphRAG 서비스 모듈 임포트
from .service import GraphRAGService, get_service


# =============================================================================
# FastAPI 앱 초기화
# =============================================================================

app = FastAPI(
    title="GraphRAG API (LangChain)",
    description="REST API for querying Neo4j using natural language with LangChain",
    version="2.0.0"
)

# GraphRAG 서비스 인스턴스 (싱글톤)
service: GraphRAGService = None


@app.on_event("startup")
async def startup_event():
    """
    서버 시작 시 GraphRAG 서비스 초기화

    FastAPI의 lifespan 이벤트를 사용해 서버 시작 시
    한 번만 서비스를 초기화합니다.
    """
    global service
    service = get_service()


# =============================================================================
# Request/Response 모델
# =============================================================================

class QueryRequest(BaseModel):
    """
    /query 엔드포인트 요청 모델

    Attributes:
        query: 사용자 질문 (필수)
        session_id: 세션 ID (선택, 기본값: "default")
        reset_context: 컨텍스트 리셋 여부 (선택, 기본값: False)
        stream: 스트리밍 응답 여부 (선택, 기본값: False)
        force_route: 강제 라우트 지정 (선택, cypher/vector/hybrid/llm_only)
    """
    query: str
    session_id: Optional[str] = "default"
    reset_context: bool = False
    stream: bool = False
    force_route: Optional[str] = None


class QueryResponse(BaseModel):
    """
    /query 엔드포인트 응답 모델 (비스트리밍)

    Attributes:
        answer: LLM이 생성한 자연어 답변
        cypher: 생성된 Cypher 쿼리
        context: Neo4j에서 가져온 원본 데이터
        route: 사용된 라우트 타입 (cypher, vector, hybrid, llm_only)
        route_reasoning: 라우팅 결정 이유
    """
    answer: str
    cypher: str
    context: list
    route: str = ""
    route_reasoning: str = ""


# =============================================================================
# API 엔드포인트
# =============================================================================

@app.get("/")
def root():
    """
    루트 엔드포인트 - 서버 상태 확인

    Returns:
        서버 정보 및 API 문서 경로
    """
    return {
        "message": "GraphRAG API Server (LangChain)",
        "docs": "/docs",
        "version": "2.0.0"
    }


@app.post("/query")
async def query(request: QueryRequest):
    """
    자연어 쿼리 처리 엔드포인트

    Query Router를 통해 쿼리 유형을 자동 분류하고
    적합한 RAG 파이프라인을 선택하여 실행합니다.

    스트리밍 여부에 따라 응답 형식이 달라집니다:
    - stream=False: JSON 응답 (QueryResponse)
    - stream=True: SSE 스트리밍 응답

    Args:
        request: QueryRequest 객체

    Returns:
        QueryResponse 또는 StreamingResponse

    Raises:
        HTTPException: 처리 중 오류 발생 시 500 에러
    """
    try:
        if request.stream:
            # 스트리밍 응답: Server-Sent Events (SSE)
            return StreamingResponse(
                service.query_stream(
                    query_text=request.query,
                    session_id=request.session_id,
                    reset_context=request.reset_context,
                    force_route=request.force_route
                ),
                media_type="text/event-stream"
            )
        else:
            # 비스트리밍 응답: JSON
            result = await service.query_async(
                query_text=request.query,
                session_id=request.session_id,
                reset_context=request.reset_context,
                force_route=request.force_route
            )

            return QueryResponse(
                answer=result.answer,
                cypher=result.cypher,
                context=result.context,
                route=result.route,
                route_reasoning=result.route_reasoning
            )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/reset/{session_id}")
def reset_session(session_id: str):
    """
    세션 컨텍스트 리셋 엔드포인트

    특정 세션의 대화 히스토리를 삭제합니다.

    Args:
        session_id: 리셋할 세션 ID (URL 경로 파라미터)

    Returns:
        성공/실패 메시지
    """
    if service.reset_session(session_id):
        return {"message": f"Session '{session_id}' context has been reset"}
    return {"message": f"Session '{session_id}' not found"}


@app.get("/sessions")
def list_sessions():
    """
    활성 세션 목록 조회 엔드포인트

    현재 서버에서 관리 중인 모든 세션 ID를 반환합니다.

    Returns:
        세션 ID 목록
    """
    return {"sessions": service.list_sessions()}


# =============================================================================
# 서버 실행
# =============================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
