"""
Log Event Schemas

Elasticsearch에 저장할 로그 이벤트 스키마 정의입니다.

스키마 구조:
- LogEvent: 최상위 로그 이벤트
  - HttpInfo: HTTP 요청/응답 정보
  - RequestInfo: 쿼리 요청 정보
  - ResponseInfo: 응답 정보
  - AgentInfo: Agent 실행 정보
  - TokenUsageInfo: 토큰 사용량
  - ClientInfo: 클라이언트 정보
"""

from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime


class HttpInfo(BaseModel):
    """
    HTTP 요청/응답 정보

    Attributes:
        method: HTTP 메서드 (GET, POST 등)
        path: 요청 경로
        status_code: HTTP 상태 코드 (응답 시)
        duration_ms: 처리 시간 (밀리초)
    """
    method: str
    path: str
    status_code: int = 0
    duration_ms: float = 0.0


class RequestInfo(BaseModel):
    """
    쿼리 요청 정보

    Attributes:
        query: 사용자 질문
        session_id: 세션 ID
        stream: 스트리밍 여부
    """
    query: str
    session_id: str
    stream: bool = False


class ResponseInfo(BaseModel):
    """
    응답 정보

    Attributes:
        answer: 최종 답변
        route: 라우팅된 파이프라인 타입 (선택)
        route_reasoning: 라우팅 결정 이유 (선택)
    """
    answer: str
    route: Optional[str] = None
    route_reasoning: Optional[str] = None


class AgentInfo(BaseModel):
    """
    Agent 실행 정보

    Attributes:
        thoughts: Agent의 추론 과정
        tool_calls: 호출된 도구 목록
        tool_results: 도구 실행 결과
        iterations: 총 반복 횟수
    """
    thoughts: List[str] = []
    tool_calls: List[Dict[str, Any]] = []
    tool_results: List[Dict[str, Any]] = []
    iterations: int = 0


class TokenUsageInfo(BaseModel):
    """
    토큰 사용량 정보

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


class ClientInfo(BaseModel):
    """
    클라이언트 정보

    Attributes:
        ip: 클라이언트 IP 주소
        user_agent: User-Agent 헤더
    """
    ip: str
    user_agent: str = ""


class LogEvent(BaseModel):
    """
    최상위 로그 이벤트

    Elasticsearch에 저장되는 단일 로그 문서입니다.

    Attributes:
        timestamp: 이벤트 발생 시간 (UTC)
        request_id: 요청 추적 ID (8자리 UUID)
        event_type: 이벤트 유형 (request, response, error)
        http: HTTP 정보
        request: 요청 정보 (선택)
        response: 응답 정보 (선택)
        agent: Agent 실행 정보 (선택)
        token_usage: 토큰 사용량 (선택)
        client: 클라이언트 정보
        error: 에러 메시지 (선택)
    """
    timestamp: datetime
    request_id: str
    event_type: str  # request, response, error
    http: HttpInfo
    request: Optional[RequestInfo] = None
    response: Optional[ResponseInfo] = None
    agent: Optional[AgentInfo] = None
    token_usage: Optional[TokenUsageInfo] = None
    client: ClientInfo
    error: Optional[str] = None

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
