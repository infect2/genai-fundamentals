"""
GraphRAG Service Module

이 모듈은 GraphRAG의 핵심 비즈니스 로직을 담당합니다.
- Neo4j 데이터베이스 연결
- LLM (Large Language Model) 설정
- GraphCypherQAChain 구성
- 세션 기반 대화 히스토리 관리
- 쿼리 실행 및 결과 처리
- Query Router를 통한 쿼리 분류 및 적합한 RAG 파이프라인 선택

API 서버와 분리하여 재사용성과 테스트 용이성을 높입니다.
"""

import os
import json
import asyncio
from typing import Optional, List, AsyncGenerator

from dotenv import load_dotenv
load_dotenv()

from langchain_neo4j import Neo4jGraph, GraphCypherQAChain, Neo4jVector, Neo4jChatMessageHistory
from langchain_core.prompts import PromptTemplate, ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

from ..tools.llm_provider import (
    create_langchain_llm,
    create_langchain_embeddings,
    get_router_model_name,
    get_token_tracker,
    check_embedding_dimension_compatibility,
)

from .models import TokenUsage, QueryResult
from .prompts import (
    CYPHER_GENERATION_TEMPLATE,
    VECTOR_RAG_TEMPLATE,
    HYBRID_RAG_TEMPLATE,
    LLM_ONLY_TEMPLATE,
)
from .router import QueryRouter, RouteType, RouteDecision
from . import pipelines


# =============================================================================
# GraphRAG 서비스 클래스
# =============================================================================

class GraphRAGService:
    """
    GraphRAG 서비스의 메인 클래스

    Neo4j 데이터베이스와 LLM을 연결하여 자연어 질문을
    Cypher 쿼리로 변환하고 결과를 자연어로 응답합니다.

    주요 기능:
    - 자연어 → Cypher 쿼리 변환
    - Neo4j 쿼리 실행
    - 세션별 대화 히스토리 관리 (Neo4j 영속화)
    - 동기/비동기 쿼리 지원
    - 스트리밍 응답 지원

    사용 예:
        service = GraphRAGService()
        result = service.query("Which actors appeared in The Matrix?")
        print(result.answer)
    """

    _CHAT_SESSION_NODE_LABEL = "ChatSession"
    _CHAT_HISTORY_WINDOW = 50

    def __init__(
        self,
        neo4j_uri: Optional[str] = None,
        neo4j_username: Optional[str] = None,
        neo4j_password: Optional[str] = None,
        model_name: Optional[str] = None,
        temperature: float = 0,
        enable_routing: bool = True
    ):
        """
        GraphRAG 서비스 초기화

        Args:
            neo4j_uri: Neo4j 연결 URI (기본값: 환경변수 NEO4J_URI)
            neo4j_username: Neo4j 사용자명 (기본값: 환경변수 NEO4J_USERNAME)
            neo4j_password: Neo4j 비밀번호 (기본값: 환경변수 NEO4J_PASSWORD)
            model_name: LLM 모델명 (기본값: 프로바이더별 환경변수)
            temperature: LLM temperature (기본값: 0, 결정론적 출력)
            enable_routing: Query Router 활성화 여부 (기본값: True)
        """
        self._neo4j_uri = neo4j_uri or os.getenv("NEO4J_URI")
        self._neo4j_username = neo4j_username or os.getenv("NEO4J_USERNAME")
        self._neo4j_password = neo4j_password or os.getenv("NEO4J_PASSWORD")
        self._enable_routing = enable_routing

        # Neo4j Driver 설정 (동시 처리 최적화)
        self._driver_config = {
            "max_connection_pool_size": int(os.getenv("NEO4J_MAX_POOL_SIZE", "100")),
            "connection_acquisition_timeout": float(os.getenv("NEO4J_CONNECTION_ACQUISITION_TIMEOUT", "60")),
            "connection_timeout": float(os.getenv("NEO4J_CONNECTION_TIMEOUT", "30")),
            "max_connection_lifetime": int(os.getenv("NEO4J_MAX_CONNECTION_LIFETIME", "3600")),
        }
        self._query_timeout = float(os.getenv("NEO4J_QUERY_TIMEOUT", "30"))

        # Neo4j 연결 설정 (커넥션 풀 최적화 적용)
        self._graph = Neo4jGraph(
            url=self._neo4j_uri,
            username=self._neo4j_username,
            password=self._neo4j_password,
            timeout=self._query_timeout,
            driver_config=self._driver_config
        )

        # 프롬프트 템플릿 생성
        self._cypher_prompt = PromptTemplate(
            input_variables=["schema", "question"],
            template=CYPHER_GENERATION_TEMPLATE
        )

        # LLM 인스턴스 생성
        self._llm = create_langchain_llm(
            model_name=model_name,
            temperature=temperature
        )

        self._streaming_llm = create_langchain_llm(
            model_name=model_name,
            temperature=temperature,
            streaming=True
        )

        # GraphCypherQAChain 생성 (Cypher RAG)
        # Note: verbose=False for MCP server compatibility (stdout must be clean JSON-RPC)
        self._chain = GraphCypherQAChain.from_llm(
            llm=self._llm,
            graph=self._graph,
            cypher_prompt=self._cypher_prompt,
            verbose=False,
            return_intermediate_steps=True,
            allow_dangerous_requests=True  # Required: LangChain safety acknowledgment
            # Security Note: Use read-only Neo4j user for protection
        )

        self._streaming_chain = GraphCypherQAChain.from_llm(
            llm=self._streaming_llm,
            graph=self._graph,
            cypher_prompt=self._cypher_prompt,
            verbose=False,
            return_intermediate_steps=True,
            allow_dangerous_requests=True  # Required: LangChain safety acknowledgment
            # Security Note: Use read-only Neo4j user for protection
        )

        # Query Router 초기화
        self._router = QueryRouter(
            llm=create_langchain_llm(model_name=get_router_model_name(), temperature=0)
        )

        # Embeddings 설정 (Vector RAG용)
        self._embeddings = create_langchain_embeddings()

        # Vector Store 초기화 (lazy initialization)
        self._vector_store = None

        # Vector RAG 프롬프트 체인 설정
        self._vector_prompt = ChatPromptTemplate.from_template(VECTOR_RAG_TEMPLATE)
        self._vector_chain = self._vector_prompt | self._llm | StrOutputParser()

        # Hybrid RAG 프롬프트 체인 설정
        self._hybrid_prompt = ChatPromptTemplate.from_template(HYBRID_RAG_TEMPLATE)
        self._hybrid_chain = self._hybrid_prompt | self._llm | StrOutputParser()

        # LLM Only 프롬프트 체인 설정
        self._llm_only_prompt = ChatPromptTemplate.from_template(LLM_ONLY_TEMPLATE)
        self._llm_only_chain = self._llm_only_prompt | self._llm | StrOutputParser()


    def _get_vector_store(self) -> Neo4jVector:
        """Vector Store lazy initialization (기존 driver 설정 재사용)"""
        if self._vector_store is None:
            check_embedding_dimension_compatibility()
            # 기존 graph의 driver 설정 재사용하여 커넥션 풀 통합
            self._vector_store = Neo4jVector.from_existing_index(
                embedding=self._embeddings,
                url=self._neo4j_uri,
                username=self._neo4j_username,
                password=self._neo4j_password,
                index_name="moviePlots",
                text_node_property="plot",
                driver_config=self._driver_config,
            )
        return self._vector_store

    # -------------------------------------------------------------------------
    # 세션 관리 메서드
    # -------------------------------------------------------------------------

    def get_or_create_history(self, session_id: str) -> Neo4jChatMessageHistory:
        """
        세션 ID에 해당하는 대화 히스토리를 가져오거나 새로 생성

        Neo4j에 영속화되므로 서버 재시작 후에도 이력이 보존됩니다.

        Args:
            session_id: 세션 식별자

        Returns:
            Neo4jChatMessageHistory 객체
        """
        return Neo4jChatMessageHistory(
            session_id=session_id,
            graph=self._graph,
            node_label=self._CHAT_SESSION_NODE_LABEL,
            window=self._CHAT_HISTORY_WINDOW,
        )

    def reset_session(self, session_id: str) -> bool:
        """
        특정 세션의 대화 히스토리 삭제

        Args:
            session_id: 삭제할 세션 ID

        Returns:
            삭제 성공 여부 (메시지가 존재했으면 True)
        """
        history = self.get_or_create_history(session_id)
        has_messages = len(history.messages) > 0
        history.clear()
        return has_messages

    def list_sessions(self) -> List[str]:
        """
        현재 활성화된 모든 세션 ID 목록 반환 (Neo4j에서 조회)

        Returns:
            세션 ID 리스트
        """
        result = self._graph.query(
            f"MATCH (s:`{self._CHAT_SESSION_NODE_LABEL}`) RETURN s.id AS session_id ORDER BY s.id"
        )
        return [record["session_id"] for record in result]

    def get_history_messages(self, session_id: str) -> List[dict]:
        """
        특정 세션의 대화 이력을 dict 리스트로 반환

        Args:
            session_id: 세션 식별자

        Returns:
            [{"role": "human"|"ai", "content": "..."}, ...] 형태의 리스트
        """
        history = self.get_or_create_history(session_id)
        return [
            {"role": msg.type, "content": msg.content}
            for msg in history.messages
        ]

    def get_schema(self) -> str:
        """
        Neo4j 데이터베이스 스키마 반환

        Agent가 데이터베이스 구조를 이해하는 데 사용합니다.

        Returns:
            데이터베이스 스키마 문자열
        """
        return self._graph.schema

    # -------------------------------------------------------------------------
    # 쿼리 실행 메서드
    # -------------------------------------------------------------------------

    def query(
        self,
        query_text: str,
        session_id: str = "default",
        reset_context: bool = False,
        force_route: Optional[str] = None
    ) -> QueryResult:
        """
        자연어 쿼리 실행 (동기 방식)

        Query Router를 통해 쿼리 유형을 분류하고
        적합한 RAG 파이프라인을 선택하여 실행합니다.

        Args:
            query_text: 사용자 질문
            session_id: 세션 ID (기본값: "default")
            reset_context: 쿼리 전 컨텍스트 리셋 여부
            force_route: 강제로 사용할 라우트 (cypher, vector, hybrid, llm_only, memory)

        Returns:
            QueryResult 객체 (answer, cypher, context, route, route_reasoning 포함)
        """
        # 컨텍스트 리셋 처리
        if reset_context:
            self.reset_session(session_id)

        # 세션 히스토리 가져오기
        history = self.get_or_create_history(session_id)

        with get_token_tracker() as cb:
            # 라우팅 결정
            if force_route:
                # 강제 라우트 지정
                route_map = {
                    "cypher": RouteType.CYPHER,
                    "vector": RouteType.VECTOR,
                    "hybrid": RouteType.HYBRID,
                    "llm_only": RouteType.LLM_ONLY,
                    "memory": RouteType.MEMORY
                }
                route_decision = RouteDecision(
                    route=route_map.get(force_route, RouteType.CYPHER),
                    confidence=1.0,
                    reasoning=f"Forced route: {force_route}"
                )
            elif self._enable_routing:
                # Query Router로 분류
                route_decision = self._router.route_sync(query_text)
            else:
                # 라우팅 비활성화시 기본 Cypher RAG
                route_decision = RouteDecision(
                    route=RouteType.CYPHER,
                    confidence=1.0,
                    reasoning="Routing disabled, using default Cypher RAG"
                )

            # 라우트별 RAG 파이프라인 실행
            if route_decision.route == RouteType.CYPHER:
                query_result = pipelines.execute_cypher_rag(
                    query_text, self._chain, route_decision
                )
            elif route_decision.route == RouteType.VECTOR:
                query_result = pipelines.execute_vector_rag(
                    query_text, self._get_vector_store(), self._vector_chain, route_decision
                )
            elif route_decision.route == RouteType.HYBRID:
                query_result = pipelines.execute_hybrid_rag(
                    query_text, self._get_vector_store(), self._chain, self._hybrid_chain, route_decision
                )
            elif route_decision.route == RouteType.MEMORY:
                query_result = pipelines.execute_memory(
                    query_text, session_id, self._llm, self._graph, route_decision
                )
            else:  # LLM_ONLY
                query_result = pipelines.execute_llm_only(
                    query_text, self._llm_only_chain, route_decision
                )

        # 토큰 사용량 기록
        query_result.token_usage = TokenUsage(
            total_tokens=cb.total_tokens,
            prompt_tokens=cb.prompt_tokens,
            completion_tokens=cb.completion_tokens,
            total_cost=cb.total_cost
        )

        # 히스토리에 저장
        history.add_user_message(query_text)
        history.add_ai_message(query_result.answer)

        return query_result

    async def query_async(
        self,
        query_text: str,
        session_id: str = "default",
        reset_context: bool = False,
        force_route: Optional[str] = None
    ) -> QueryResult:
        """
        자연어 쿼리 실행 (비동기 방식)

        동기 query() 메서드를 비동기로 래핑하여
        이벤트 루프 블로킹을 방지합니다.

        Args:
            query_text: 사용자 질문
            session_id: 세션 ID
            reset_context: 쿼리 전 컨텍스트 리셋 여부
            force_route: 강제로 사용할 라우트 (cypher, vector, hybrid, llm_only, memory)

        Returns:
            QueryResult 객체
        """
        return await asyncio.to_thread(
            self.query, query_text, session_id, reset_context, force_route
        )

    async def query_stream(
        self,
        query_text: str,
        session_id: str = "default",
        reset_context: bool = False,
        chunk_size: int = 10,
        force_route: Optional[str] = None
    ) -> AsyncGenerator[str, None]:
        """
        SSE 형식으로 스트리밍 응답 생성

        응답 순서:
        1. metadata: Cypher 쿼리, 컨텍스트, 라우트 정보
        2. token: 답변 텍스트를 청크 단위로 전송
        3. done: 스트리밍 완료 신호

        Args:
            query_text: 사용자 질문
            session_id: 세션 ID
            reset_context: 쿼리 전 컨텍스트 리셋 여부
            chunk_size: 스트리밍 청크 크기 (문자 단위)
            force_route: 강제로 사용할 라우트 (cypher, vector, hybrid, llm_only, memory)

        Yields:
            SSE 형식 문자열 ("data: {...}\\n\\n")
        """
        # 컨텍스트 리셋 처리
        if reset_context:
            self.reset_session(session_id)

        # 세션 히스토리 가져오기
        history = self.get_or_create_history(session_id)

        # 쿼리 실행 (라우팅 포함, 비동기)
        query_result = await asyncio.to_thread(
            lambda: self.query(query_text, session_id, False, force_route)
        )

        # Step 1: 메타데이터 전송 (라우팅 정보 포함)
        metadata = {
            "type": "metadata",
            "cypher": query_result.cypher,
            "context": query_result.context,
            "route": query_result.route,
            "route_reasoning": query_result.route_reasoning
        }
        yield f"data: {json.dumps(metadata)}\n\n"

        # Step 2: 답변 텍스트 스트리밍
        full_answer = query_result.answer
        for i in range(0, len(full_answer), chunk_size):
            chunk = full_answer[i:i+chunk_size]
            token_data = {"type": "token", "content": chunk}
            yield f"data: {json.dumps(token_data)}\n\n"
            await asyncio.sleep(0.05)

        # Step 3: 완료 신호 (토큰 사용량 포함)
        done_data = {"type": "done"}
        if query_result.token_usage:
            done_data["token_usage"] = {
                "total_tokens": query_result.token_usage.total_tokens,
                "prompt_tokens": query_result.token_usage.prompt_tokens,
                "completion_tokens": query_result.token_usage.completion_tokens,
                "total_cost": query_result.token_usage.total_cost
            }
        yield f"data: {json.dumps(done_data)}\n\n"


# =============================================================================
# 싱글톤 인스턴스 (선택적 사용)
# =============================================================================

# 전역 서비스 인스턴스 (필요시 사용)
_service_instance: Optional[GraphRAGService] = None

def get_service() -> GraphRAGService:
    """
    GraphRAGService 싱글톤 인스턴스 반환

    애플리케이션 전체에서 하나의 서비스 인스턴스를 공유할 때 사용합니다.

    Returns:
        GraphRAGService 인스턴스
    """
    global _service_instance
    if _service_instance is None:
        _service_instance = GraphRAGService()
    return _service_instance
