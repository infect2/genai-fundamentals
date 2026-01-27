"""
Capora AI Ontology Bot - REST API Server (Agent-Only + Multi-Agent v2)

FastAPI 기반의 REST API 서버입니다.
기존 단일 에이전트 API와 멀티 에이전트 v2 API를 모두 제공합니다.

엔드포인트:
- GET  /              : 서버 상태 확인
- POST /agent/query   : Agent 쿼리 실행 (스트리밍/비스트리밍)
- POST /reset/{id}    : 세션 컨텍스트 리셋
- GET  /sessions      : 활성 세션 목록
- GET  /history/{id}  : 대화 이력 조회

v2 엔드포인트 (멀티 에이전트):
- POST /v2/query      : 멀티 에이전트 쿼리 실행 (도메인 자동 라우팅)
- GET  /v2/agents     : 등록된 도메인 에이전트 목록
- GET  /v2/agents/{domain}/schema : 도메인별 온톨로지 스키마

실행 방법:
    python -m genai-fundamentals.api.server
    또는
    uvicorn genai-fundamentals.api.server:app --reload
"""

import time

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional

# Ontology 서비스 모듈 임포트
from .graphrag_service import GraphRAGService, get_service
from .agent import AgentService

# 멀티 에이전트 모듈 임포트
from .multi_agents import get_registry, DomainType
from .multi_agents.orchestrator import OrchestratorService, get_orchestrator

# Elasticsearch 로깅 모듈 임포트
from .logging import ElasticsearchLoggingMiddleware, log_agent_response, ES_ENABLED


# =============================================================================
# FastAPI 앱 초기화
# =============================================================================

app = FastAPI(
    title="Capora AI Ontology Bot API",
    description="REST API for querying Neo4j knowledge graph using natural language",
    version="2.0.0"
)

# Elasticsearch 로깅 미들웨어 등록
app.add_middleware(ElasticsearchLoggingMiddleware)

# 서비스 인스턴스 (싱글톤)
service: GraphRAGService = None
agent_service: AgentService = None
orchestrator_service: OrchestratorService = None


@app.on_event("startup")
async def startup_event():
    """
    서버 시작 시 서비스 초기화

    FastAPI의 lifespan 이벤트를 사용해 서버 시작 시
    한 번만 서비스를 초기화합니다.
    """
    global service, agent_service, orchestrator_service
    service = get_service()
    agent_service = AgentService(service)

    # 멀티 에이전트 시스템 초기화
    _initialize_multi_agent_system()
    orchestrator_service = get_orchestrator(graphrag_service=service)


def _initialize_multi_agent_system():
    """
    멀티 에이전트 시스템 초기화

    도메인 에이전트들을 레지스트리에 등록합니다.
    """
    registry = get_registry()

    # TMS Agent 등록
    try:
        from .multi_agents.tms import TMSAgent
        tms_agent = TMSAgent(graphrag_service=service)
        registry.register(tms_agent)
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"Failed to register TMS agent: {e}")

    # WMS Agent 등록 (구현 시)
    try:
        from .multi_agents.wms import WMSAgent
        wms_agent = WMSAgent(graphrag_service=service)
        registry.register(wms_agent)
    except (ImportError, Exception):
        pass  # 아직 구현되지 않음

    # FMS Agent 등록 (구현 시)
    try:
        from .multi_agents.fms import FMSAgent
        fms_agent = FMSAgent(graphrag_service=service)
        registry.register(fms_agent)
    except (ImportError, Exception):
        pass

    # TAP Agent 등록 (구현 시)
    try:
        from .multi_agents.tap import TAPAgent
        tap_agent = TAPAgent(graphrag_service=service)
        registry.register(tap_agent)
    except (ImportError, Exception):
        pass


# =============================================================================
# Request/Response 모델
# =============================================================================

class TokenUsageResponse(BaseModel):
    """
    토큰 사용량 응답 모델

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


class AgentQueryRequest(BaseModel):
    """
    /agent/query 엔드포인트 요청 모델

    Attributes:
        query: 사용자 질문 (필수)
        session_id: 세션 ID (선택, 기본값: "default")
        stream: 스트리밍 응답 여부 (선택, 기본값: False)
    """
    query: str
    session_id: Optional[str] = "default"
    stream: bool = False


class AgentQueryResponse(BaseModel):
    """
    /agent/query 엔드포인트 응답 모델 (비스트리밍)

    Attributes:
        answer: Agent가 생성한 최종 답변
        thoughts: Agent의 추론 과정
        tool_calls: 호출된 도구 목록
        tool_results: 도구 실행 결과
        iterations: 총 반복 횟수
        token_usage: LLM 토큰 사용량
    """
    answer: str
    thoughts: list
    tool_calls: list
    tool_results: list
    iterations: int
    token_usage: Optional[TokenUsageResponse] = None


# =============================================================================
# v2 Request/Response 모델 (멀티 에이전트)
# =============================================================================

class MultiAgentQueryRequest(BaseModel):
    """
    /v2/query 엔드포인트 요청 모델

    Attributes:
        query: 사용자 질문 (필수)
        session_id: 세션 ID (선택, 기본값: "default")
        preferred_domain: 선호 도메인 ("auto"면 자동 라우팅)
        allow_cross_domain: 크로스 도메인 처리 허용 여부
        stream: 스트리밍 응답 여부
    """
    query: str
    session_id: Optional[str] = "default"
    preferred_domain: str = "auto"
    allow_cross_domain: bool = True
    stream: bool = False


class DomainDecisionResponse(BaseModel):
    """도메인 라우팅 결정 응답 모델"""
    primary: str
    secondary: list
    confidence: float
    reasoning: str
    cross_domain: bool


class MultiAgentQueryResponse(BaseModel):
    """
    /v2/query 엔드포인트 응답 모델

    Attributes:
        answer: 통합된 최종 답변
        domain_decision: 도메인 라우팅 결정
        agent_results: 도메인별 실행 결과
        token_usage: 총 토큰 사용량
    """
    answer: str
    domain_decision: DomainDecisionResponse
    agent_results: dict
    token_usage: Optional[TokenUsageResponse] = None


class AgentInfoResponse(BaseModel):
    """에이전트 정보 응답 모델"""
    domain: str
    description: str
    tools_count: int
    keywords: list


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
        "message": "Capora AI Ontology Bot API Server",
        "docs": "/docs",
        "version": "2.0.0"
    }


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


@app.get("/history/{session_id}")
def get_history(session_id: str):
    """
    세션 대화 이력 조회 엔드포인트

    특정 세션의 전체 대화 이력을 반환합니다.

    Args:
        session_id: 조회할 세션 ID (URL 경로 파라미터)

    Returns:
        세션 ID와 메시지 목록
    """
    messages = service.get_history_messages(session_id)
    return {"session_id": session_id, "messages": messages}


@app.get("/cache/stats")
def get_cache_stats():
    """
    캐시 및 동시성 통계 조회 엔드포인트

    쿼리 캐시, Request Coalescer, LLM Semaphore의 현재 상태를 반환합니다.

    Returns:
        - cache: 캐시 통계 (size, hits, misses, hit_rate, coalesced)
        - coalescer: Request Coalescing 통계 (in_flight, coalesced, executed)
        - semaphore: LLM Semaphore 통계 (current, max_concurrent, utilization)
    """
    return agent_service.get_cache_stats()


@app.post("/cache/clear")
def clear_cache():
    """
    캐시 초기화 엔드포인트

    모든 캐시된 쿼리 결과를 삭제합니다.

    Returns:
        삭제된 엔트리 수
    """
    from .cache import get_cache
    cache = get_cache()
    cleared = cache.invalidate()
    return {"cleared": cleared, "message": f"Cleared {cleared} cache entries"}


@app.post("/agent/query")
async def agent_query(request: AgentQueryRequest, req: Request):
    """
    ReAct Agent를 사용한 자연어 쿼리 처리 엔드포인트

    Multi-step reasoning을 통해 쿼리를 처리합니다.
    여러 도구(cypher_query, vector_search, hybrid_search 등)를
    조합하여 답변을 생성합니다.

    스트리밍 여부에 따라 응답 형식이 달라집니다:
    - stream=False: JSON 응답 (AgentQueryResponse)
    - stream=True: SSE 스트리밍 응답

    Args:
        request: AgentQueryRequest 객체
        req: FastAPI Request 객체 (로깅용)

    Returns:
        AgentQueryResponse 또는 StreamingResponse

    Raises:
        HTTPException: 처리 중 오류 발생 시 500 에러
    """
    # Request ID 가져오기 (미들웨어에서 설정)
    request_id = getattr(req.state, "request_id", "unknown")
    start_time = time.time()

    try:
        if request.stream:
            # 스트리밍 응답: Server-Sent Events (SSE)
            return StreamingResponse(
                agent_service.query_stream(
                    query_text=request.query,
                    session_id=request.session_id
                ),
                media_type="text/event-stream"
            )
        else:
            # 비스트리밍 응답: JSON
            result = await agent_service.query_async(
                query_text=request.query,
                session_id=request.session_id
            )

            # 처리 시간 계산
            duration_ms = (time.time() - start_time) * 1000

            # Elasticsearch에 상세 Agent 응답 로깅
            if ES_ENABLED:
                await log_agent_response(
                    request_id=request_id,
                    request=req,
                    query=request.query,
                    session_id=request.session_id,
                    stream=request.stream,
                    result=result,
                    duration_ms=duration_ms
                )

            token_usage = None
            if result.token_usage:
                token_usage = TokenUsageResponse(
                    total_tokens=result.token_usage.total_tokens,
                    prompt_tokens=result.token_usage.prompt_tokens,
                    completion_tokens=result.token_usage.completion_tokens,
                    total_cost=result.token_usage.total_cost
                )

            return AgentQueryResponse(
                answer=result.answer,
                thoughts=result.thoughts,
                tool_calls=result.tool_calls,
                tool_results=result.tool_results,
                iterations=result.iterations,
                token_usage=token_usage
            )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# v2 엔드포인트 (멀티 에이전트)
# =============================================================================

@app.post("/v2/query")
async def multi_agent_query(request: MultiAgentQueryRequest, req: Request):
    """
    멀티 에이전트 쿼리 처리 엔드포인트 (v2)

    사용자 쿼리를 분석하여 적합한 도메인 에이전트로 라우팅하고,
    단일/크로스 도메인 쿼리를 처리합니다.

    스트리밍 여부에 따라 응답 형식이 달라집니다:
    - stream=False: JSON 응답 (MultiAgentQueryResponse)
    - stream=True: SSE 스트리밍 응답 (domain_decision → token → done)

    Args:
        request: MultiAgentQueryRequest 객체
        req: FastAPI Request 객체

    Returns:
        MultiAgentQueryResponse 또는 StreamingResponse

    Raises:
        HTTPException: 처리 중 오류 발생 시 500 에러
    """
    try:
        if request.stream:
            # 스트리밍 응답: Server-Sent Events (SSE)
            return StreamingResponse(
                orchestrator_service.query_stream(
                    query_text=request.query,
                    session_id=request.session_id,
                    preferred_domain=request.preferred_domain,
                    allow_cross_domain=request.allow_cross_domain
                ),
                media_type="text/event-stream"
            )
        else:
            # 비스트리밍 응답: JSON
            result = await orchestrator_service.query_async(
                query_text=request.query,
                session_id=request.session_id,
                preferred_domain=request.preferred_domain,
                allow_cross_domain=request.allow_cross_domain
            )

            token_usage = None
            if result.token_usage:
                token_usage = TokenUsageResponse(
                    total_tokens=result.token_usage.total_tokens,
                    prompt_tokens=result.token_usage.prompt_tokens,
                    completion_tokens=result.token_usage.completion_tokens,
                    total_cost=result.token_usage.total_cost
                )

            return MultiAgentQueryResponse(
                answer=result.answer,
                domain_decision=DomainDecisionResponse(**result.domain_decision),
                agent_results=result.agent_results,
                token_usage=token_usage
            )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/v2/agents")
def list_agents():
    """
    등록된 도메인 에이전트 목록 조회 엔드포인트

    Returns:
        에이전트 정보 목록 (도메인, 설명, 도구 수, 키워드)
    """
    registry = get_registry()
    agents_info = registry.get_agent_info()
    return {
        "agents": agents_info,
        "count": len(agents_info)
    }


@app.get("/v2/agents/{domain}/schema")
def get_domain_schema(domain: str):
    """
    특정 도메인의 온톨로지 스키마 조회 엔드포인트

    Args:
        domain: 도메인 이름 (wms, tms, fms, tap)

    Returns:
        도메인 스키마 정보

    Raises:
        HTTPException: 도메인을 찾을 수 없는 경우 404 에러
    """
    registry = get_registry()
    agent = registry.get_by_name(domain)

    if not agent:
        raise HTTPException(status_code=404, detail=f"Domain '{domain}' not found")

    return {
        "domain": domain,
        "schema": agent.get_schema_subset(),
        "description": agent.description
    }


# =============================================================================
# 서버 실행
# =============================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
