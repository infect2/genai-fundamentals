"""
Query Router Tests

Query Router의 분류 기능과 라우팅 로직을 테스트합니다.

실행 방법:
    # 모든 Router 테스트 실행
    pytest genai-fundamentals/tests/test_router.py -v

    # Mock LLM 테스트만 실행 (API 호출 없음)
    pytest genai-fundamentals/tests/test_router.py -v -k "mock"

    # 통합 테스트 (API 호출 필요)
    pytest genai-fundamentals/tests/test_router.py -v -k "integration"
"""

import sys
import os

# Add the parent directory to sys.path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from unittest.mock import Mock, patch, AsyncMock

from api.router import (
    QueryRouter,
    RouteType,
    RouteDecision,
    CLASSIFICATION_PROMPT
)


class TestRouteType:
    """RouteType enum 테스트"""

    def test_route_type_values(self):
        """모든 라우트 타입 값 확인"""
        assert RouteType.CYPHER.value == "cypher"
        assert RouteType.VECTOR.value == "vector"
        assert RouteType.HYBRID.value == "hybrid"
        assert RouteType.LLM_ONLY.value == "llm_only"

    def test_route_type_count(self):
        """라우트 타입 개수 확인"""
        assert len(RouteType) == 4


class TestRouteDecision:
    """RouteDecision dataclass 테스트"""

    def test_route_decision_creation(self):
        """RouteDecision 생성 테스트"""
        decision = RouteDecision(
            route=RouteType.CYPHER,
            confidence=0.95,
            reasoning="특정 배우 이름이 언급됨"
        )

        assert decision.route == RouteType.CYPHER
        assert decision.confidence == 0.95
        assert decision.reasoning == "특정 배우 이름이 언급됨"


class TestQueryRouterMock:
    """QueryRouter Mock 테스트 (LLM 호출 없음)"""

    def test_parse_response_cypher(self):
        """Cypher 라우트 응답 파싱"""
        router = QueryRouter.__new__(QueryRouter)

        response = """route: cypher
confidence: 0.95
reasoning: 특정 배우 이름이 언급되어 엔티티 조회가 필요합니다."""

        decision = router._parse_response(response)

        assert decision.route == RouteType.CYPHER
        assert decision.confidence == 0.95
        assert "배우" in decision.reasoning

    def test_parse_response_vector(self):
        """Vector 라우트 응답 파싱"""
        router = QueryRouter.__new__(QueryRouter)

        response = """route: vector
confidence: 0.88
reasoning: 줄거리나 분위기로 검색하는 시맨틱 쿼리입니다."""

        decision = router._parse_response(response)

        assert decision.route == RouteType.VECTOR
        assert decision.confidence == 0.88
        assert "시맨틱" in decision.reasoning

    def test_parse_response_hybrid(self):
        """Hybrid 라우트 응답 파싱"""
        router = QueryRouter.__new__(QueryRouter)

        response = """route: hybrid
confidence: 0.82
reasoning: 시맨틱 검색과 필터링이 모두 필요합니다."""

        decision = router._parse_response(response)

        assert decision.route == RouteType.HYBRID
        assert decision.confidence == 0.82

    def test_parse_response_llm_only(self):
        """LLM Only 라우트 응답 파싱"""
        router = QueryRouter.__new__(QueryRouter)

        response = """route: llm_only
confidence: 0.99
reasoning: 일반적인 질문으로 DB 조회가 필요 없습니다."""

        decision = router._parse_response(response)

        assert decision.route == RouteType.LLM_ONLY
        assert decision.confidence == 0.99

    def test_parse_response_default(self):
        """알 수 없는 라우트 기본값 처리"""
        router = QueryRouter.__new__(QueryRouter)

        response = """route: unknown_route
confidence: 0.5
reasoning: 알 수 없는 쿼리 유형"""

        decision = router._parse_response(response)

        # 기본값은 CYPHER
        assert decision.route == RouteType.CYPHER

    def test_parse_response_invalid_confidence(self):
        """잘못된 신뢰도 값 처리"""
        router = QueryRouter.__new__(QueryRouter)

        response = """route: cypher
confidence: invalid
reasoning: 테스트"""

        decision = router._parse_response(response)

        # 기본값 0.8
        assert decision.confidence == 0.8

    @patch('api.router.ChatOpenAI')
    def test_router_initialization(self, mock_chat):
        """라우터 초기화 테스트"""
        mock_llm = Mock()
        mock_chat.return_value = mock_llm

        router = QueryRouter(llm=mock_llm)

        assert router._llm == mock_llm
        assert router._prompt is not None

    def test_route_sync(self):
        """동기 라우팅 테스트"""
        mock_llm = Mock()
        mock_chain = Mock()
        mock_chain.invoke.return_value = """route: cypher
confidence: 0.9
reasoning: 특정 영화 제목 검색"""

        router = QueryRouter.__new__(QueryRouter)
        router._llm = mock_llm
        router._chain = mock_chain

        decision = router.route_sync("매트릭스 출연 배우는?")

        assert decision.route == RouteType.CYPHER
        mock_chain.invoke.assert_called_once()


class TestQueryRouterExamples:
    """라우팅 예제 테스트 (응답 파싱)"""

    @pytest.fixture
    def router(self):
        """테스트용 라우터 인스턴스"""
        return QueryRouter.__new__(QueryRouter)

    @pytest.mark.parametrize("query,expected_route,response", [
        # Cypher 쿼리 예제
        ("톰 행크스가 출연한 영화는?", RouteType.CYPHER,
         "route: cypher\nconfidence: 0.95\nreasoning: 특정 배우 이름 검색"),
        ("매트릭스의 감독은 누구인가요?", RouteType.CYPHER,
         "route: cypher\nconfidence: 0.92\nreasoning: 특정 영화의 감독 조회"),
        ("액션 장르 영화 목록", RouteType.CYPHER,
         "route: cypher\nconfidence: 0.88\nreasoning: 장르별 필터링"),

        # Vector 쿼리 예제
        ("슬픈 영화 추천해줘", RouteType.VECTOR,
         "route: vector\nconfidence: 0.90\nreasoning: 분위기 기반 시맨틱 검색"),
        ("우주를 배경으로 한 영화", RouteType.VECTOR,
         "route: vector\nconfidence: 0.87\nreasoning: 테마 기반 검색"),
        ("반전이 있는 스릴러", RouteType.VECTOR,
         "route: vector\nconfidence: 0.85\nreasoning: 줄거리 특성 검색"),

        # Hybrid 쿼리 예제
        ("90년대 액션 영화 중 평점 높은 것", RouteType.HYBRID,
         "route: hybrid\nconfidence: 0.83\nreasoning: 필터링과 시맨틱 검색 조합"),
        ("톰 행크스 영화 중 감동적인 것", RouteType.HYBRID,
         "route: hybrid\nconfidence: 0.80\nreasoning: 특정 배우 + 분위기 검색"),

        # LLM Only 예제
        ("영화란 무엇인가요?", RouteType.LLM_ONLY,
         "route: llm_only\nconfidence: 0.98\nreasoning: 일반 지식 질문"),
        ("안녕하세요", RouteType.LLM_ONLY,
         "route: llm_only\nconfidence: 0.99\nreasoning: 인사말"),
        ("감사합니다", RouteType.LLM_ONLY,
         "route: llm_only\nconfidence: 0.99\nreasoning: 감사 표현"),
    ])
    def test_route_examples(self, router, query, expected_route, response):
        """라우팅 예제별 응답 파싱 테스트"""
        decision = router._parse_response(response)
        assert decision.route == expected_route


class TestClassificationPrompt:
    """분류 프롬프트 테스트"""

    def test_prompt_contains_all_routes(self):
        """프롬프트에 모든 라우트 타입 포함 확인"""
        assert "cypher" in CLASSIFICATION_PROMPT
        assert "vector" in CLASSIFICATION_PROMPT
        assert "hybrid" in CLASSIFICATION_PROMPT
        assert "llm_only" in CLASSIFICATION_PROMPT

    def test_prompt_has_query_placeholder(self):
        """프롬프트에 쿼리 플레이스홀더 확인"""
        assert "{query}" in CLASSIFICATION_PROMPT

    def test_prompt_has_response_format(self):
        """프롬프트에 응답 형식 설명 포함 확인"""
        assert "route:" in CLASSIFICATION_PROMPT
        assert "confidence:" in CLASSIFICATION_PROMPT
        assert "reasoning:" in CLASSIFICATION_PROMPT


@pytest.mark.integration
class TestQueryRouterIntegration:
    """QueryRouter 통합 테스트 (실제 API 호출)

    주의: 이 테스트는 OpenAI API를 호출합니다.
    OPENAI_API_KEY 환경변수가 설정되어 있어야 합니다.
    """

    @pytest.fixture
    def router(self):
        """실제 LLM을 사용하는 라우터"""
        from dotenv import load_dotenv
        load_dotenv()
        return QueryRouter()

    @pytest.mark.asyncio
    async def test_route_cypher_query(self, router):
        """Cypher 쿼리 라우팅 통합 테스트"""
        decision = await router.route("톰 행크스가 출연한 영화는?")

        # 실제 LLM 응답이므로 정확한 값 검증은 어려움
        assert decision.route in [RouteType.CYPHER, RouteType.HYBRID]
        assert decision.confidence > 0
        assert len(decision.reasoning) > 0

    @pytest.mark.asyncio
    async def test_route_vector_query(self, router):
        """Vector 쿼리 라우팅 통합 테스트"""
        decision = await router.route("슬픈 영화 추천해줘")

        assert decision.route in [RouteType.VECTOR, RouteType.HYBRID]
        assert decision.confidence > 0

    @pytest.mark.asyncio
    async def test_route_llm_only_query(self, router):
        """LLM Only 쿼리 라우팅 통합 테스트"""
        decision = await router.route("안녕하세요")

        assert decision.route == RouteType.LLM_ONLY
        assert decision.confidence > 0.8

    def test_route_sync_cypher(self, router):
        """동기 Cypher 쿼리 라우팅 테스트"""
        decision = router.route_sync("매트릭스 출연 배우 목록")

        assert decision.route in [RouteType.CYPHER, RouteType.HYBRID]
        assert decision.confidence > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
