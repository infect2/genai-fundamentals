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
from dataclasses import dataclass, field
from typing import Optional, List, AsyncGenerator

from dotenv import load_dotenv
load_dotenv()

from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_neo4j import Neo4jGraph, GraphCypherQAChain, Neo4jVector, Neo4jChatMessageHistory
from langchain_core.prompts import PromptTemplate, ChatPromptTemplate
from langchain_core.callbacks import BaseCallbackHandler
from langchain_community.callbacks import get_openai_callback
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough

from .router import QueryRouter, RouteType, RouteDecision


# =============================================================================
# 데이터 클래스 정의
# =============================================================================

@dataclass
class TokenUsage:
    """
    LLM 토큰 사용량을 담는 데이터 클래스

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


@dataclass
class QueryResult:
    """
    쿼리 실행 결과를 담는 데이터 클래스

    Attributes:
        answer: LLM이 생성한 자연어 답변
        cypher: 생성된 Cypher 쿼리
        context: Neo4j에서 가져온 원본 데이터 리스트
        route: 사용된 라우트 타입 (cypher, vector, hybrid, llm_only)
        route_reasoning: 라우팅 결정 이유
        token_usage: LLM 토큰 사용량
    """
    answer: str
    cypher: str
    context: List[str]
    route: str = ""
    route_reasoning: str = ""
    token_usage: Optional[TokenUsage] = None


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
# Vector RAG 프롬프트 템플릿
# =============================================================================

VECTOR_RAG_TEMPLATE = """You are a movie recommendation assistant.
Use the following movie information retrieved from the database to answer the user's question.

Retrieved Movies:
{context}

User Question: {question}

Instructions:
- Based on the retrieved movie information, provide a helpful answer
- If multiple movies are relevant, list them with brief explanations
- If no relevant movies are found, acknowledge this and suggest alternatives
- Be conversational and helpful

Answer:"""


# =============================================================================
# Hybrid RAG 프롬프트 템플릿
# =============================================================================

HYBRID_RAG_TEMPLATE = """You are a movie expert assistant.
Use both the semantic search results and structured data to answer the user's question.

Semantic Search Results (similar movies by plot/theme):
{vector_context}

Structured Data Results (from database query):
{cypher_context}

User Question: {question}

Instructions:
- Combine information from both sources for a comprehensive answer
- Prioritize accuracy from structured data
- Use semantic results for recommendations and comparisons
- Be specific and include movie titles, actors, directors when relevant

Answer:"""


# =============================================================================
# LLM Only 프롬프트 템플릿
# =============================================================================

LLM_ONLY_TEMPLATE = """You are a helpful general-purpose assistant.

User Question: {question}

Instructions:
- Answer the question based on your general knowledge
- If the question is about movies, provide detailed movie-related information
- If the question is about other topics (math, science, coding, etc.), answer helpfully
- If the question is a greeting or casual conversation, respond appropriately
- Keep responses concise and helpful
- Respond in the same language as the user's question

Answer:"""


# =============================================================================
# 메모리 추출 프롬프트 템플릿
# =============================================================================

MEMORY_EXTRACT_TEMPLATE = """사용자의 메시지에서 저장할 정보를 추출하세요.

메시지: {message}

JSON 형식으로 응답하세요:
{{"action": "store" 또는 "recall", "key": "정보 종류 (예: 차번호, 이메일, 전화번호)", "value": "저장할 값 (store인 경우만)"}}

store 예시:
- "내 차번호는 59구8426이야" → {{"action": "store", "key": "차번호", "value": "59구8426"}}
- "내 이메일은 test@email.com이야 기억해" → {{"action": "store", "key": "이메일", "value": "test@email.com"}}

recall 예시:
- "내 차번호 뭐지?" → {{"action": "recall", "key": "차번호", "value": ""}}
- "내 이메일 알려줘" → {{"action": "recall", "key": "이메일", "value": ""}}
"""


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
    _USER_MEMORY_NODE_LABEL = "UserMemory"

    def __init__(
        self,
        neo4j_uri: Optional[str] = None,
        neo4j_username: Optional[str] = None,
        neo4j_password: Optional[str] = None,
        model_name: str = "gpt-4o",
        temperature: float = 0,
        enable_routing: bool = True
    ):
        """
        GraphRAG 서비스 초기화

        Args:
            neo4j_uri: Neo4j 연결 URI (기본값: 환경변수 NEO4J_URI)
            neo4j_username: Neo4j 사용자명 (기본값: 환경변수 NEO4J_USERNAME)
            neo4j_password: Neo4j 비밀번호 (기본값: 환경변수 NEO4J_PASSWORD)
            model_name: OpenAI 모델명 (기본값: "gpt-4o")
            temperature: LLM temperature (기본값: 0, 결정론적 출력)
            enable_routing: Query Router 활성화 여부 (기본값: True)
        """
        self._neo4j_uri = neo4j_uri or os.getenv("NEO4J_URI")
        self._neo4j_username = neo4j_username or os.getenv("NEO4J_USERNAME")
        self._neo4j_password = neo4j_password or os.getenv("NEO4J_PASSWORD")
        self._enable_routing = enable_routing

        # Neo4j 연결 설정
        self._graph = Neo4jGraph(
            url=self._neo4j_uri,
            username=self._neo4j_username,
            password=self._neo4j_password
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

        # GraphCypherQAChain 생성 (Cypher RAG)
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

        # Query Router 초기화
        self._router = QueryRouter(llm=ChatOpenAI(model="gpt-4o-mini", temperature=0))

        # Embeddings 설정 (Vector RAG용)
        self._embeddings = OpenAIEmbeddings(model="text-embedding-ada-002")

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
        """Vector Store lazy initialization"""
        if self._vector_store is None:
            self._vector_store = Neo4jVector.from_existing_index(
                embedding=self._embeddings,
                url=self._neo4j_uri,
                username=self._neo4j_username,
                password=self._neo4j_password,
                index_name="moviePlots",
                text_node_property="plot",
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
    # 메모리 저장/조회 메서드
    # -------------------------------------------------------------------------

    def store_user_memory(self, session_id: str, key: str, value: str) -> None:
        """
        사용자 정보를 Neo4j에 저장 (MERGE로 upsert)

        Args:
            session_id: 세션 식별자
            key: 정보 종류 (예: 차번호, 이메일)
            value: 저장할 값
        """
        self._graph.query(
            f"""
            MERGE (m:`{self._USER_MEMORY_NODE_LABEL}` {{session_id: $session_id, key: $key}})
            SET m.value = $value, m.updated_at = datetime()
            """,
            params={"session_id": session_id, "key": key, "value": value}
        )

    def get_user_memory(self, session_id: str, key: str) -> Optional[str]:
        """
        저장된 사용자 정보 조회

        Args:
            session_id: 세션 식별자
            key: 정보 종류

        Returns:
            저장된 값 또는 None
        """
        result = self._graph.query(
            f"""
            MATCH (m:`{self._USER_MEMORY_NODE_LABEL}` {{session_id: $session_id, key: $key}})
            RETURN m.value AS value
            """,
            params={"session_id": session_id, "key": key}
        )
        return result[0]["value"] if result else None

    def get_all_user_memories(self, session_id: str) -> List[dict]:
        """
        세션의 모든 저장된 정보 조회

        Args:
            session_id: 세션 식별자

        Returns:
            [{"key": "...", "value": "..."}, ...] 형태의 리스트
        """
        result = self._graph.query(
            f"""
            MATCH (m:`{self._USER_MEMORY_NODE_LABEL}` {{session_id: $session_id}})
            RETURN m.key AS key, m.value AS value
            ORDER BY m.key
            """,
            params={"session_id": session_id}
        )
        return [{"key": r["key"], "value": r["value"]} for r in result]

    def execute_memory(
        self,
        query_text: str,
        session_id: str,
        route_decision: RouteDecision
    ) -> QueryResult:
        """
        MEMORY 라우트 실행 (사용자 정보 저장/조회)

        LLM으로 사용자 메시지에서 action/key/value를 추출한 후
        store면 Neo4j에 저장, recall이면 조회하여 응답합니다.

        Args:
            query_text: 사용자 메시지
            session_id: 세션 식별자
            route_decision: 라우팅 결정 정보

        Returns:
            QueryResult 객체
        """
        extract_result = self._llm.invoke(
            MEMORY_EXTRACT_TEMPLATE.format(message=query_text)
        )
        # LLM이 markdown 코드블록으로 감싸는 경우 처리
        content = extract_result.content.strip()
        if content.startswith("```"):
            content = content.split("\n", 1)[1]  # 첫 줄(```json) 제거
            content = content.rsplit("```", 1)[0]  # 마지막 ``` 제거
        parsed = json.loads(content.strip())

        action = parsed.get("action", "recall")
        key = parsed.get("key", "")
        value = parsed.get("value", "")

        if action == "store" and key and value:
            self.store_user_memory(session_id, key, value)
            answer = f"'{key}' 정보를 기억했습니다: {value}"
        else:
            stored_value = self.get_user_memory(session_id, key)
            if stored_value:
                answer = f"{key}은(는) {stored_value}입니다."
            else:
                answer = f"저장된 '{key}' 정보가 없습니다."

        return QueryResult(
            answer=answer,
            cypher="",
            context=[],
            route=route_decision.route.value,
            route_reasoning=route_decision.reasoning
        )

    # -------------------------------------------------------------------------
    # RAG 파이프라인 실행 메서드
    # -------------------------------------------------------------------------

    def execute_cypher_rag(
        self,
        query_text: str,
        route_decision: Optional[RouteDecision] = None
    ) -> QueryResult:
        """
        Cypher RAG 파이프라인 실행 (Text-to-Cypher)

        Args:
            query_text: 사용자 질문
            route_decision: 라우팅 결정 정보

        Returns:
            QueryResult 객체
        """
        result = self._chain.invoke({"query": query_text})
        cypher, context = self._extract_intermediate_steps(result)

        route_value = route_decision.route.value if route_decision else "cypher"
        route_reasoning = route_decision.reasoning if route_decision else ""

        return QueryResult(
            answer=result["result"],
            cypher=cypher,
            context=context,
            route=route_value,
            route_reasoning=route_reasoning
        )

    def execute_vector_rag(
        self,
        query_text: str,
        route_decision: Optional[RouteDecision] = None,
        top_k: int = 5
    ) -> QueryResult:
        """
        Vector RAG 파이프라인 실행 (시맨틱 검색)

        Args:
            query_text: 사용자 질문
            route_decision: 라우팅 결정 정보
            top_k: 검색할 문서 수

        Returns:
            QueryResult 객체
        """
        # Vector Store에서 유사 문서 검색
        vector_store = self._get_vector_store()
        docs = vector_store.similarity_search(query_text, k=top_k)

        # 컨텍스트 구성
        context_parts = []
        for i, doc in enumerate(docs, 1):
            title = doc.metadata.get("title", "Unknown")
            plot = doc.page_content
            context_parts.append(f"{i}. {title}: {plot[:200]}...")

        context_str = "\n".join(context_parts)

        # LLM으로 답변 생성
        answer = self._vector_chain.invoke({
            "context": context_str,
            "question": query_text
        })

        route_value = route_decision.route.value if route_decision else "vector"
        route_reasoning = route_decision.reasoning if route_decision else ""

        return QueryResult(
            answer=answer,
            cypher="",  # Vector RAG는 Cypher를 사용하지 않음
            context=[str(doc.metadata) for doc in docs],
            route=route_value,
            route_reasoning=route_reasoning
        )

    def execute_hybrid_rag(
        self,
        query_text: str,
        route_decision: Optional[RouteDecision] = None,
        top_k: int = 3
    ) -> QueryResult:
        """
        Hybrid RAG 파이프라인 실행 (Vector + Cypher)

        Args:
            query_text: 사용자 질문
            route_decision: 라우팅 결정 정보
            top_k: 벡터 검색 문서 수

        Returns:
            QueryResult 객체
        """
        # 1. Vector 검색
        vector_store = self._get_vector_store()
        docs = vector_store.similarity_search(query_text, k=top_k)

        vector_context_parts = []
        for i, doc in enumerate(docs, 1):
            title = doc.metadata.get("title", "Unknown")
            plot = doc.page_content
            vector_context_parts.append(f"{i}. {title}: {plot[:200]}...")

        vector_context_str = "\n".join(vector_context_parts)

        # 2. Cypher 쿼리 실행
        cypher_result = self._chain.invoke({"query": query_text})
        cypher, cypher_context = self._extract_intermediate_steps(cypher_result)

        cypher_context_str = "\n".join(cypher_context) if cypher_context else "No structured data found."

        # 3. Hybrid 답변 생성
        answer = self._hybrid_chain.invoke({
            "vector_context": vector_context_str,
            "cypher_context": cypher_context_str,
            "question": query_text
        })

        # 컨텍스트 통합
        combined_context = [
            f"[Vector] {str(doc.metadata)}" for doc in docs
        ] + [
            f"[Cypher] {c}" for c in cypher_context
        ]

        route_value = route_decision.route.value if route_decision else "hybrid"
        route_reasoning = route_decision.reasoning if route_decision else ""

        return QueryResult(
            answer=answer,
            cypher=cypher,
            context=combined_context,
            route=route_value,
            route_reasoning=route_reasoning
        )

    def execute_llm_only(
        self,
        query_text: str,
        route_decision: Optional[RouteDecision] = None
    ) -> QueryResult:
        """
        LLM Only 파이프라인 실행 (DB 조회 없이 직접 응답)

        Args:
            query_text: 사용자 질문
            route_decision: 라우팅 결정 정보

        Returns:
            QueryResult 객체
        """
        answer = self._llm_only_chain.invoke({"question": query_text})

        route_value = route_decision.route.value if route_decision else "llm_only"
        route_reasoning = route_decision.reasoning if route_decision else ""

        return QueryResult(
            answer=answer,
            cypher="",  # LLM Only는 Cypher 없음
            context=[],  # 컨텍스트 없음
            route=route_value,
            route_reasoning=route_reasoning
        )

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
            force_route: 강제로 사용할 라우트 (cypher, vector, hybrid, llm_only)

        Returns:
            QueryResult 객체 (answer, cypher, context, route, route_reasoning 포함)
        """
        # 컨텍스트 리셋 처리
        if reset_context:
            self.reset_session(session_id)

        # 세션 히스토리 가져오기
        history = self.get_or_create_history(session_id)

        with get_openai_callback() as cb:
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
                query_result = self.execute_cypher_rag(query_text, route_decision)
            elif route_decision.route == RouteType.VECTOR:
                query_result = self.execute_vector_rag(query_text, route_decision)
            elif route_decision.route == RouteType.HYBRID:
                query_result = self.execute_hybrid_rag(query_text, route_decision)
            elif route_decision.route == RouteType.MEMORY:
                query_result = self.execute_memory(query_text, session_id, route_decision)
            else:  # LLM_ONLY
                query_result = self.execute_llm_only(query_text, route_decision)

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
            force_route: 강제로 사용할 라우트 (cypher, vector, hybrid, llm_only)

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
            force_route: 강제로 사용할 라우트 (cypher, vector, hybrid, llm_only)

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
