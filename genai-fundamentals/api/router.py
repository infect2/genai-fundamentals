"""
Query Router Module

쿼리 유형에 따라 적합한 RAG 파이프라인을 선택하는 라우터입니다.

라우트 타입:
- cypher: Text-to-Cypher (엔티티/관계 조회)
- vector: Vector search (시맨틱/유사도 검색)
- hybrid: Vector + Cypher (복합 쿼리)
- llm_only: LLM 직접 응답 (DB 불필요)
- memory:  사용자 정보 저장/조회
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate

from ..tools.llm_provider import create_langchain_llm, get_router_model_name


class RouteType(Enum):
    """쿼리 라우트 타입"""

    CYPHER = "cypher"  # Text-to-Cypher (엔티티/관계 조회)
    VECTOR = "vector"  # Vector search (시맨틱/유사도 검색)
    HYBRID = "hybrid"  # Vector + Cypher (복합 쿼리)
    LLM_ONLY = "llm_only"  # LLM 직접 응답 (DB 불필요)
    MEMORY = "memory"  # 사용자 정보 저장/조회


@dataclass
class RouteDecision:
    """
    라우팅 결정 결과

    Attributes:
        route: 선택된 라우트 타입
        confidence: 결정 신뢰도 (0.0-1.0)
        reasoning: 라우팅 결정 이유
    """

    route: RouteType
    confidence: float
    reasoning: str


# =============================================================================
# 분류 프롬프트 템플릿
# =============================================================================

CLASSIFICATION_PROMPT = """당신은 지식 그래프 쿼리 분류 전문가입니다.
사용자 쿼리를 분석하여 가장 적합한 처리 방식을 선택하세요.

## 라우트 타입

1. **cypher**: 특정 엔티티나 관계를 조회하는 쿼리
   - 특정 엔티티 이름이나 ID로 검색
   - 관계 기반 질문 (누가 연결되어 있는지, 어떤 관계인지)
   - 정확한 이름/식별자가 언급된 경우
   - 예시: "X와 연결된 엔티티는?", "Y의 속성은?", "특정 유형의 노드 목록"

2. **vector**: 시맨틱/의미 기반 검색이 필요한 쿼리
   - 설명, 내용, 테마 기반 검색
   - 유사한 엔티티 찾기
   - 설명이나 의미로 검색
   - 예시: "비슷한 특성을 가진 엔티티 찾아줘", "이런 내용을 가진 데이터"

3. **hybrid**: 시맨틱 검색 + 필터/조건 조합
   - 의미 검색과 특정 조건 모두 필요
   - 예시: "특정 속성을 가진 엔티티 중 유사한 것", "X 유형 중 특정 조건"

4. **llm_only**: 지식 그래프 조회가 필요 없는 일반 질문
   - 일반 상식, 정의
   - 인사말, 감사 표현
   - DB에 없는 정보 요청
   - 예시: "이것은 무엇인가요?", "안녕하세요", "감사합니다"

5. **memory**: 사용자가 개인 정보를 저장하거나 조회하려는 쿼리
   - 정보를 기억/저장해달라는 요청
   - 이전에 저장한 정보를 물어보는 요청
   - 예시: "내 차번호는 59구8426이야 기억해", "내 차번호 뭐지?", "내 이메일 알려줘"

## 쿼리 분석

Query: {query}

## 응답 형식 (정확히 이 형식으로 응답하세요)

route: [cypher|vector|hybrid|llm_only|memory]
confidence: [0.0-1.0]
reasoning: [한 문장으로 이유 설명]"""


class QueryRouter:
    """
    쿼리 라우터

    LLM을 사용하여 사용자 쿼리를 분류하고
    적합한 RAG 파이프라인을 선택합니다.

    사용 예:
        router = QueryRouter(llm)
        decision = await router.route("X와 연결된 엔티티는?")
        print(decision.route)  # RouteType.CYPHER
    """

    def __init__(self, llm=None):
        """
        QueryRouter 초기화

        Args:
            llm: 분류에 사용할 LLM 인스턴스 (None이면 기본 생성)
        """
        self._llm = llm or create_langchain_llm(
            model_name=get_router_model_name(), temperature=0
        )

        self._prompt = PromptTemplate(
            input_variables=["query"], template=CLASSIFICATION_PROMPT
        )

        self._chain = self._prompt | self._llm | StrOutputParser()

    def _parse_response(self, response: str) -> RouteDecision:
        """
        LLM 응답 파싱

        Args:
            response: LLM의 텍스트 응답

        Returns:
            RouteDecision 객체
        """
        lines = response.strip().split("\n")

        route_str = "cypher"
        confidence = 0.8
        reasoning = ""

        for line in lines:
            line = line.strip()
            if line.lower().startswith("route:"):
                route_str = line.split(":", 1)[1].strip().lower()
            elif line.lower().startswith("confidence:"):
                try:
                    confidence = float(line.split(":", 1)[1].strip())
                except ValueError:
                    confidence = 0.8
            elif line.lower().startswith("reasoning:"):
                reasoning = line.split(":", 1)[1].strip()

        # RouteType으로 변환
        route_map = {
            "cypher": RouteType.CYPHER,
            "vector": RouteType.VECTOR,
            "hybrid": RouteType.HYBRID,
            "llm_only": RouteType.LLM_ONLY,
            "memory": RouteType.MEMORY,
        }
        route = route_map.get(route_str, RouteType.CYPHER)

        return RouteDecision(route=route, confidence=confidence, reasoning=reasoning)

    async def route(self, query: str) -> RouteDecision:
        """
        쿼리 라우팅 결정 (비동기)

        Args:
            query: 사용자 쿼리

        Returns:
            RouteDecision 객체
        """
        response = await self._chain.ainvoke({"query": query})
        return self._parse_response(response)

    def route_sync(self, query: str) -> RouteDecision:
        """
        쿼리 라우팅 결정 (동기)

        Args:
            query: 사용자 쿼리

        Returns:
            RouteDecision 객체
        """
        response = self._chain.invoke({"query": query})
        return self._parse_response(response)
