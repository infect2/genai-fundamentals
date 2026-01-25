"""
FastAPI Elasticsearch Logging Middleware

모든 HTTP 요청/응답을 Elasticsearch에 로깅합니다.

기능:
- Request 시작 시 로깅
- Response 완료 시 로깅 (처리 시간 포함)
- 에러 발생 시 에러 로깅
- 스트리밍 응답은 request만 로깅

주의:
- ES_LOGGING_ENABLED가 false면 미들웨어가 bypass됩니다.
- Elasticsearch 연결 실패 시에도 요청 처리는 계속됩니다.
"""

import time
import uuid
import json
import logging
from datetime import datetime
from typing import Optional, Dict, Any

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response, StreamingResponse

from .config import get_es_client, get_index_name, ES_ENABLED
from .schemas import (
    LogEvent,
    HttpInfo,
    RequestInfo,
    ResponseInfo,
    AgentInfo,
    TokenUsageInfo,
    ClientInfo,
)

logger = logging.getLogger(__name__)


async def log_to_elasticsearch(log_event: LogEvent):
    """
    로그 이벤트를 Elasticsearch에 비동기로 저장

    Args:
        log_event: 저장할 로그 이벤트
    """
    es = get_es_client()
    if not es:
        return

    try:
        # Pydantic 모델을 dict로 변환
        doc = log_event.model_dump(mode="json")
        es.index(index=get_index_name(), document=doc)
    except Exception as e:
        logger.error(f"ES logging failed: {e}")


async def log_agent_response(
    request_id: str,
    request: Request,
    query: str,
    session_id: str,
    stream: bool,
    result: Any,
    duration_ms: float
):
    """
    Agent 쿼리 응답을 상세하게 로깅

    /agent/query 엔드포인트의 응답을 Elasticsearch에 로깅합니다.
    Agent의 추론 과정, 도구 호출, 토큰 사용량 등을 포함합니다.

    Args:
        request_id: 요청 추적 ID
        request: FastAPI Request 객체
        query: 사용자 질문
        session_id: 세션 ID
        stream: 스트리밍 여부
        result: AgentResult 객체
        duration_ms: 처리 시간 (밀리초)
    """
    if not ES_ENABLED:
        return

    # Agent 정보 구성
    agent_info = None
    if hasattr(result, 'thoughts'):
        agent_info = AgentInfo(
            thoughts=result.thoughts or [],
            tool_calls=result.tool_calls or [],
            tool_results=result.tool_results or [],
            iterations=result.iterations or 0
        )

    # 토큰 사용량 정보 구성
    token_usage_info = None
    if hasattr(result, 'token_usage') and result.token_usage:
        token_usage_info = TokenUsageInfo(
            total_tokens=result.token_usage.total_tokens,
            prompt_tokens=result.token_usage.prompt_tokens,
            completion_tokens=result.token_usage.completion_tokens,
            total_cost=result.token_usage.total_cost
        )

    log_event = LogEvent(
        timestamp=datetime.utcnow(),
        request_id=request_id,
        event_type="agent_response",
        http=HttpInfo(
            method=request.method,
            path=str(request.url.path),
            status_code=200,
            duration_ms=duration_ms
        ),
        request=RequestInfo(
            query=query,
            session_id=session_id,
            stream=stream
        ),
        response=ResponseInfo(
            answer=result.answer if hasattr(result, 'answer') else ""
        ),
        agent=agent_info,
        token_usage=token_usage_info,
        client=ClientInfo(
            ip=request.client.host if request.client else "unknown",
            user_agent=request.headers.get("user-agent", "")
        )
    )

    await log_to_elasticsearch(log_event)


class ElasticsearchLoggingMiddleware(BaseHTTPMiddleware):
    """
    FastAPI 미들웨어: 모든 요청/응답을 Elasticsearch에 로깅

    사용법:
        app.add_middleware(ElasticsearchLoggingMiddleware)

    동작:
    1. 요청 시작 시 request_id 생성
    2. Request 로깅 (POST 요청의 경우 body 포함)
    3. 응답 처리 후 Response 로깅 (처리 시간 포함)
    4. 에러 발생 시 에러 로깅
    """

    async def dispatch(self, request: Request, call_next):
        """
        미들웨어 dispatch 메서드

        모든 요청을 가로채서 로깅 후 다음 핸들러로 전달합니다.
        """
        # ES 로깅 비활성화 시 bypass
        if not ES_ENABLED:
            return await call_next(request)

        # Request ID 생성 (8자리 UUID)
        request_id = str(uuid.uuid4())[:8]
        request.state.request_id = request_id

        # 시작 시간 기록
        start_time = time.time()

        # Request body 캡처 (POST 요청만)
        request_body = None
        if request.method == "POST":
            try:
                body_bytes = await request.body()
                request_body = json.loads(body_bytes)
                # Body 재설정 (consume 후 복원)
                # Note: FastAPI의 body() 메서드는 캐싱됨
            except json.JSONDecodeError:
                request_body = {}
            except Exception:
                request_body = {}

        # Request 로깅
        await self._log_request(request, request_id, request_body)

        # 에러 처리를 위한 try-except
        try:
            # 실제 요청 처리
            response = await call_next(request)

            # 응답 시간 계산
            duration_ms = (time.time() - start_time) * 1000

            # Response 로깅 (스트리밍 응답 제외)
            # 스트리밍 응답은 agent_query 엔드포인트에서 별도 처리
            if not isinstance(response, StreamingResponse):
                await self._log_response(
                    request, response, request_id, duration_ms
                )

            return response

        except Exception as e:
            # 에러 로깅
            duration_ms = (time.time() - start_time) * 1000
            await self._log_error(request, request_id, str(e), duration_ms)
            raise

    async def _log_request(
        self,
        request: Request,
        request_id: str,
        body: Optional[Dict[str, Any]]
    ):
        """
        Request 로깅

        Args:
            request: FastAPI Request 객체
            request_id: 요청 추적 ID
            body: 요청 body (POST 요청의 경우)
        """
        # 쿼리 요청 정보 추출
        request_info = None
        if body and "query" in body:
            request_info = RequestInfo(
                query=body.get("query", ""),
                session_id=body.get("session_id", "default"),
                stream=body.get("stream", False)
            )

        log_event = LogEvent(
            timestamp=datetime.utcnow(),
            request_id=request_id,
            event_type="request",
            http=HttpInfo(
                method=request.method,
                path=str(request.url.path),
                status_code=0,
                duration_ms=0.0
            ),
            request=request_info,
            client=ClientInfo(
                ip=request.client.host if request.client else "unknown",
                user_agent=request.headers.get("user-agent", "")
            )
        )

        await log_to_elasticsearch(log_event)

    async def _log_response(
        self,
        request: Request,
        response: Response,
        request_id: str,
        duration_ms: float
    ):
        """
        Response 로깅

        Args:
            request: FastAPI Request 객체
            response: Starlette Response 객체
            request_id: 요청 추적 ID
            duration_ms: 처리 시간 (밀리초)
        """
        log_event = LogEvent(
            timestamp=datetime.utcnow(),
            request_id=request_id,
            event_type="response",
            http=HttpInfo(
                method=request.method,
                path=str(request.url.path),
                status_code=response.status_code,
                duration_ms=duration_ms
            ),
            client=ClientInfo(
                ip=request.client.host if request.client else "unknown",
                user_agent=request.headers.get("user-agent", "")
            )
        )

        await log_to_elasticsearch(log_event)

    async def _log_error(
        self,
        request: Request,
        request_id: str,
        error_message: str,
        duration_ms: float
    ):
        """
        Error 로깅

        Args:
            request: FastAPI Request 객체
            request_id: 요청 추적 ID
            error_message: 에러 메시지
            duration_ms: 처리 시간 (밀리초)
        """
        log_event = LogEvent(
            timestamp=datetime.utcnow(),
            request_id=request_id,
            event_type="error",
            http=HttpInfo(
                method=request.method,
                path=str(request.url.path),
                status_code=500,
                duration_ms=duration_ms
            ),
            client=ClientInfo(
                ip=request.client.host if request.client else "unknown",
                user_agent=request.headers.get("user-agent", "")
            ),
            error=error_message
        )

        await log_to_elasticsearch(log_event)
