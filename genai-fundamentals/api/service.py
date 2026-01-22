"""
GraphRAG Service Module

이 모듈은 GraphRAG의 핵심 비즈니스 로직을 담당합니다.
- Neo4j 데이터베이스 연결
- LLM (Large Language Model) 설정
- GraphCypherQAChain 구성
- 세션 기반 대화 히스토리 관리
- 쿼리 실행 및 결과 처리

API 서버와 분리하여 재사용성과 테스트 용이성을 높입니다.
"""

import os
import json
import asyncio
from dataclasses import dataclass
from typing import Optional, List, AsyncGenerator

from dotenv import load_dotenv
load_dotenv()

from langchain_openai import ChatOpenAI
from langchain_neo4j import Neo4jGraph, GraphCypherQAChain
from langchain_community.chat_message_histories import ChatMessageHistory
from langchain_core.prompts import PromptTemplate
from langchain_core.callbacks import BaseCallbackHandler


# =============================================================================
# 데이터 클래스 정의
# =============================================================================

@dataclass
class QueryResult:
    """
    쿼리 실행 결과를 담는 데이터 클래스

    Attributes:
        answer: LLM이 생성한 자연어 답변
        cypher: 생성된 Cypher 쿼리
        context: Neo4j에서 가져온 원본 데이터 리스트
    """
    answer: str
    cypher: str
    context: List[str]


# =============================================================================
# Cypher 생성 프롬프트 템플릿
# =============================================================================

CYPHER_GENERATION_TEMPLATE = """You are an expert Neo4j Cypher translator.
Convert the user's natural language question into a Cypher query.

Schema:
{schema}

Important notes:
- Movie titles with articles are stored as "Title, The" format (e.g., "Matrix, The", "Godfather, The")
- Use case-insensitive matching when possible

Examples:
Q: Which actors appeared in The Matrix?
Cypher: MATCH (a:Actor)-[:ACTED_IN]->(m:Movie) WHERE m.title = 'Matrix, The' RETURN a.name

Q: What movies did Tom Hanks star in?
Cypher: MATCH (a:Actor {{name: 'Tom Hanks'}})-[:ACTED_IN]->(m:Movie) RETURN m.title

Q: What genre is Toy Story?
Cypher: MATCH (m:Movie {{title: 'Toy Story'}})-[:IN_GENRE]->(g:Genre) RETURN g.name

Q: Who directed The Godfather?
Cypher: MATCH (d:Director)-[:DIRECTED]->(m:Movie) WHERE m.title = 'Godfather, The' RETURN d.name

Question: {question}
Cypher:"""


# =============================================================================
# 스트리밍 콜백 핸들러
# =============================================================================

class StreamingCallbackHandler(BaseCallbackHandler):
    """
    LLM의 스트리밍 출력을 처리하는 콜백 핸들러

    LangChain의 콜백 시스템을 활용해 LLM이 토큰을 생성할 때마다
    실시간으로 처리할 수 있습니다.
    """

    def __init__(self):
        self.tokens = []
        self.queue = asyncio.Queue()
        self.done = False

    def on_llm_new_token(self, token: str, **kwargs):
        """새 토큰이 생성될 때마다 호출"""
        self.tokens.append(token)
        asyncio.get_event_loop().call_soon_threadsafe(
            self.queue.put_nowait, token
        )

    def on_llm_end(self, response, **kwargs):
        """LLM 생성 완료 시 호출"""
        self.done = True
        asyncio.get_event_loop().call_soon_threadsafe(
            self.queue.put_nowait, None
        )


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
    - 세션별 대화 히스토리 관리
    - 동기/비동기 쿼리 지원
    - 스트리밍 응답 지원

    사용 예:
        service = GraphRAGService()
        result = service.query("Which actors appeared in The Matrix?")
        print(result.answer)
    """

    def __init__(
        self,
        neo4j_uri: Optional[str] = None,
        neo4j_username: Optional[str] = None,
        neo4j_password: Optional[str] = None,
        model_name: str = "gpt-4o",
        temperature: float = 0
    ):
        """
        GraphRAG 서비스 초기화

        Args:
            neo4j_uri: Neo4j 연결 URI (기본값: 환경변수 NEO4J_URI)
            neo4j_username: Neo4j 사용자명 (기본값: 환경변수 NEO4J_USERNAME)
            neo4j_password: Neo4j 비밀번호 (기본값: 환경변수 NEO4J_PASSWORD)
            model_name: OpenAI 모델명 (기본값: "gpt-4o")
            temperature: LLM temperature (기본값: 0, 결정론적 출력)
        """
        # Neo4j 연결 설정
        self._graph = Neo4jGraph(
            url=neo4j_uri or os.getenv("NEO4J_URI"),
            username=neo4j_username or os.getenv("NEO4J_USERNAME"),
            password=neo4j_password or os.getenv("NEO4J_PASSWORD")
        )

        # 프롬프트 템플릿 생성
        self._cypher_prompt = PromptTemplate(
            input_variables=["schema", "question"],
            template=CYPHER_GENERATION_TEMPLATE
        )

        # LLM 인스턴스 생성
        self._llm = ChatOpenAI(
            model=model_name,
            temperature=temperature
        )

        self._streaming_llm = ChatOpenAI(
            model=model_name,
            temperature=temperature,
            streaming=True
        )

        # GraphCypherQAChain 생성
        # Note: verbose=False for MCP server compatibility (stdout must be clean JSON-RPC)
        self._chain = GraphCypherQAChain.from_llm(
            llm=self._llm,
            graph=self._graph,
            cypher_prompt=self._cypher_prompt,
            verbose=False,
            return_intermediate_steps=True,
            allow_dangerous_requests=True
        )

        self._streaming_chain = GraphCypherQAChain.from_llm(
            llm=self._streaming_llm,
            graph=self._graph,
            cypher_prompt=self._cypher_prompt,
            verbose=False,
            return_intermediate_steps=True,
            allow_dangerous_requests=True
        )

        # 세션 히스토리 저장소
        self._session_histories: dict[str, ChatMessageHistory] = {}

    # -------------------------------------------------------------------------
    # 세션 관리 메서드
    # -------------------------------------------------------------------------

    def get_or_create_history(self, session_id: str) -> ChatMessageHistory:
        """
        세션 ID에 해당하는 대화 히스토리를 가져오거나 새로 생성

        Args:
            session_id: 세션 식별자

        Returns:
            ChatMessageHistory 객체
        """
        if session_id not in self._session_histories:
            self._session_histories[session_id] = ChatMessageHistory()
        return self._session_histories[session_id]

    def reset_session(self, session_id: str) -> bool:
        """
        특정 세션의 대화 히스토리 삭제

        Args:
            session_id: 삭제할 세션 ID

        Returns:
            삭제 성공 여부 (세션이 존재했으면 True)
        """
        if session_id in self._session_histories:
            del self._session_histories[session_id]
            return True
        return False

    def list_sessions(self) -> List[str]:
        """
        현재 활성화된 모든 세션 ID 목록 반환

        Returns:
            세션 ID 리스트
        """
        return list(self._session_histories.keys())

    # -------------------------------------------------------------------------
    # 쿼리 실행 메서드
    # -------------------------------------------------------------------------

    def _extract_intermediate_steps(self, result: dict) -> tuple[str, List[str]]:
        """
        Chain 실행 결과에서 Cypher 쿼리와 컨텍스트 추출

        Args:
            result: chain.invoke() 반환값

        Returns:
            (cypher_query, context_list) 튜플
        """
        cypher = ""
        context = []

        if "intermediate_steps" in result:
            for step in result["intermediate_steps"]:
                if isinstance(step, dict):
                    if "query" in step:
                        cypher = step["query"]
                    if "context" in step:
                        ctx = step["context"]
                        context = ctx if isinstance(ctx, list) else [ctx]

        return cypher, [str(c) for c in context]

    def query(
        self,
        query_text: str,
        session_id: str = "default",
        reset_context: bool = False
    ) -> QueryResult:
        """
        자연어 쿼리 실행 (동기 방식)

        Args:
            query_text: 사용자 질문
            session_id: 세션 ID (기본값: "default")
            reset_context: 쿼리 전 컨텍스트 리셋 여부

        Returns:
            QueryResult 객체 (answer, cypher, context 포함)
        """
        # 컨텍스트 리셋 처리
        if reset_context:
            self.reset_session(session_id)

        # 세션 히스토리 가져오기
        history = self.get_or_create_history(session_id)

        # Chain 실행
        result = self._chain.invoke({"query": query_text})

        # 히스토리에 저장
        history.add_user_message(query_text)
        history.add_ai_message(result["result"])

        # 중간 단계에서 정보 추출
        cypher, context = self._extract_intermediate_steps(result)

        return QueryResult(
            answer=result["result"],
            cypher=cypher,
            context=context
        )

    async def query_async(
        self,
        query_text: str,
        session_id: str = "default",
        reset_context: bool = False
    ) -> QueryResult:
        """
        자연어 쿼리 실행 (비동기 방식)

        동기 query() 메서드를 비동기로 래핑하여
        이벤트 루프 블로킹을 방지합니다.

        Args:
            query_text: 사용자 질문
            session_id: 세션 ID
            reset_context: 쿼리 전 컨텍스트 리셋 여부

        Returns:
            QueryResult 객체
        """
        return await asyncio.to_thread(
            self.query, query_text, session_id, reset_context
        )

    async def query_stream(
        self,
        query_text: str,
        session_id: str = "default",
        reset_context: bool = False,
        chunk_size: int = 10
    ) -> AsyncGenerator[str, None]:
        """
        SSE 형식으로 스트리밍 응답 생성

        응답 순서:
        1. metadata: Cypher 쿼리와 컨텍스트 정보
        2. token: 답변 텍스트를 청크 단위로 전송
        3. done: 스트리밍 완료 신호

        Args:
            query_text: 사용자 질문
            session_id: 세션 ID
            reset_context: 쿼리 전 컨텍스트 리셋 여부
            chunk_size: 스트리밍 청크 크기 (문자 단위)

        Yields:
            SSE 형식 문자열 ("data: {...}\\n\\n")
        """
        # 컨텍스트 리셋 처리
        if reset_context:
            self.reset_session(session_id)

        # 세션 히스토리 가져오기
        history = self.get_or_create_history(session_id)

        # 쿼리 실행 (비동기)
        result = await asyncio.to_thread(
            lambda: self._chain.invoke({"query": query_text})
        )

        # 중간 단계에서 정보 추출
        cypher, context = self._extract_intermediate_steps(result)

        # Step 1: 메타데이터 전송
        metadata = {
            "type": "metadata",
            "cypher": cypher,
            "context": context
        }
        yield f"data: {json.dumps(metadata)}\n\n"

        # Step 2: 답변 텍스트 스트리밍
        full_answer = result["result"]
        for i in range(0, len(full_answer), chunk_size):
            chunk = full_answer[i:i+chunk_size]
            token_data = {"type": "token", "content": chunk}
            yield f"data: {json.dumps(token_data)}\n\n"
            await asyncio.sleep(0.05)

        # Step 3: 히스토리 저장
        history.add_user_message(query_text)
        history.add_ai_message(full_answer)

        # Step 4: 완료 신호
        yield f"data: {json.dumps({'type': 'done'})}\n\n"


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
