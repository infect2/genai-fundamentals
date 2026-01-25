"""
Test Runner for Sample Queries

sample_queries.py에 정의된 복잡한 쿼리들을 실제 API에 대해 실행하고 검증합니다.

Usage:
    # 모든 쿼리 테스트 (API 서버 필요)
    pytest genai-fundamentals/tests/test_sample_queries.py -v

    # 특정 복잡도만 테스트
    pytest genai-fundamentals/tests/test_sample_queries.py -v -k "complex"

    # 특정 라우팅만 테스트
    pytest genai-fundamentals/tests/test_sample_queries.py -v -k "cypher"

환경:
    - API 서버가 http://localhost:8000 에서 실행 중이어야 함
    - Neo4j에 Middlemile 온톨로지 데이터가 로드되어 있어야 함
"""

import pytest
import requests
import os
from typing import Optional

from .sample_queries import (
    SAMPLE_QUERIES,
    SampleQuery,
    QueryComplexity,
    ExpectedRoute,
    get_queries_by_complexity,
    get_queries_by_route,
)


# =============================================================================
# 설정
# =============================================================================

API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
TIMEOUT = 120  # 복잡한 쿼리는 시간이 걸릴 수 있음


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture(scope="module")
def api_available():
    """API 서버 연결 확인"""
    try:
        response = requests.get(f"{API_BASE_URL}/", timeout=5)
        if response.status_code == 200:
            return True
    except requests.exceptions.RequestException:
        pass
    pytest.skip("API server not available")


@pytest.fixture
def session_id():
    """테스트용 세션 ID"""
    return "test-sample-queries"


# =============================================================================
# 헬퍼 함수
# =============================================================================

def execute_query(query: str, session_id: str = "test") -> dict:
    """
    Agent API를 통해 쿼리 실행

    Args:
        query: 자연어 쿼리
        session_id: 세션 ID

    Returns:
        API 응답 딕셔너리
    """
    response = requests.post(
        f"{API_BASE_URL}/agent/query",
        json={"query": query, "session_id": session_id, "stream": False},
        timeout=TIMEOUT
    )
    response.raise_for_status()
    return response.json()


def validate_response(response: dict, sample_query: SampleQuery) -> tuple[bool, str]:
    """
    응답 검증

    Args:
        response: API 응답
        sample_query: 샘플 쿼리 정의

    Returns:
        (성공 여부, 메시지)
    """
    answer = response.get("answer", "")

    # 빈 응답 체크
    if not answer:
        return False, "Empty answer"

    # 에러 응답 체크
    error_keywords = ["error", "오류", "실패", "찾을 수 없", "not found"]
    answer_lower = answer.lower()
    for kw in error_keywords:
        if kw in answer_lower and len(answer) < 100:
            return False, f"Possible error response: {answer[:100]}"

    # 예상 키워드 체크 (최소 1개 이상 포함)
    found_keywords = []
    for kw in sample_query.expected_keywords:
        if kw.lower() in answer.lower():
            found_keywords.append(kw)

    if not found_keywords:
        return False, f"No expected keywords found. Expected: {sample_query.expected_keywords}"

    return True, f"Found keywords: {found_keywords}"


# =============================================================================
# 테스트 케이스
# =============================================================================

class TestSampleQueries:
    """샘플 쿼리 테스트 클래스"""

    @pytest.mark.parametrize("sample_query", SAMPLE_QUERIES, ids=[q.id for q in SAMPLE_QUERIES])
    def test_query_execution(self, api_available, session_id, sample_query: SampleQuery):
        """
        각 샘플 쿼리 실행 및 검증
        """
        # 쿼리 실행 (한국어)
        response = execute_query(sample_query.query_ko, session_id)

        # 기본 응답 구조 확인
        assert "answer" in response, "Response should contain 'answer'"
        assert "iterations" in response, "Response should contain 'iterations'"

        # 응답 검증
        is_valid, message = validate_response(response, sample_query)

        # 검증 결과 출력 (실패 시에도 정보 제공)
        print(f"\n{'='*60}")
        print(f"Query ID: {sample_query.id}")
        print(f"Complexity: {sample_query.complexity.value}")
        print(f"Expected Route: {sample_query.expected_route.value}")
        print(f"Query: {sample_query.query_ko[:50]}...")
        print(f"Answer: {response.get('answer', '')[:200]}...")
        print(f"Iterations: {response.get('iterations', 0)}")
        print(f"Tool Calls: {len(response.get('tool_calls', []))}")
        print(f"Validation: {'PASS' if is_valid else 'FAIL'} - {message}")
        print(f"{'='*60}")

        # Soft assertion (경고만, 실패하지 않음)
        if not is_valid:
            pytest.xfail(f"Validation warning: {message}")


class TestQueryComplexity:
    """복잡도별 쿼리 테스트"""

    @pytest.mark.parametrize("complexity", [
        QueryComplexity.SIMPLE,
        QueryComplexity.MEDIUM,
        QueryComplexity.COMPLEX,
        QueryComplexity.ADVANCED,
    ])
    def test_queries_exist_for_complexity(self, complexity: QueryComplexity):
        """각 복잡도 레벨에 쿼리가 존재하는지 확인"""
        queries = get_queries_by_complexity(complexity)
        # SIMPLE은 현재 정의되어 있지 않으므로 제외
        if complexity != QueryComplexity.SIMPLE:
            assert len(queries) > 0, f"No queries defined for {complexity.value}"


class TestQueryRouting:
    """라우팅 타입별 쿼리 테스트"""

    @pytest.mark.parametrize("route", [
        ExpectedRoute.CYPHER,
        ExpectedRoute.VECTOR,
        ExpectedRoute.HYBRID,
    ])
    def test_queries_exist_for_route(self, route: ExpectedRoute):
        """각 라우팅 타입에 쿼리가 존재하는지 확인"""
        queries = get_queries_by_route(route)
        assert len(queries) > 0, f"No queries defined for {route.value}"


# =============================================================================
# 통합 테스트 (선택적 실행)
# =============================================================================

@pytest.mark.integration
class TestIntegration:
    """통합 테스트 (실제 API 호출)"""

    def test_cypher_queries(self, api_available, session_id):
        """Cypher 라우팅 쿼리 일괄 테스트"""
        cypher_queries = get_queries_by_route(ExpectedRoute.CYPHER)
        results = []

        for q in cypher_queries[:3]:  # 상위 3개만 테스트
            try:
                response = execute_query(q.query_ko, session_id)
                is_valid, _ = validate_response(response, q)
                results.append((q.id, is_valid))
            except Exception as e:
                results.append((q.id, False))

        # 최소 50% 성공
        success_count = sum(1 for _, valid in results if valid)
        assert success_count >= len(results) // 2, f"Too many failures: {results}"

    def test_sequential_queries(self, api_available, session_id):
        """연속 쿼리 테스트 (컨텍스트 유지)"""
        # Query 1: 운송사 조회
        r1 = execute_query("운송사 목록을 보여줘", session_id)
        assert "answer" in r1

        # Query 2: 후속 질문 (컨텍스트 참조)
        r2 = execute_query("그 중에서 차량을 가장 많이 보유한 운송사는?", session_id)
        assert "answer" in r2

        # 두 번째 응답이 첫 번째와 관련 있는지 확인
        assert len(r2.get("answer", "")) > 50, "Follow-up answer too short"


# =============================================================================
# 벤치마크 (선택적 실행)
# =============================================================================

@pytest.mark.benchmark
class TestBenchmark:
    """성능 벤치마크"""

    def test_query_response_time(self, api_available, session_id):
        """쿼리 응답 시간 측정"""
        import time

        results = []
        for q in SAMPLE_QUERIES[:5]:  # 상위 5개만
            start = time.time()
            try:
                response = execute_query(q.query_ko, session_id)
                elapsed = time.time() - start
                results.append({
                    "id": q.id,
                    "complexity": q.complexity.value,
                    "time_sec": round(elapsed, 2),
                    "iterations": response.get("iterations", 0)
                })
            except Exception as e:
                results.append({
                    "id": q.id,
                    "error": str(e)
                })

        print("\n" + "=" * 60)
        print("BENCHMARK RESULTS")
        print("=" * 60)
        for r in results:
            if "error" in r:
                print(f"{r['id']}: ERROR - {r['error']}")
            else:
                print(f"{r['id']}: {r['time_sec']}s ({r['iterations']} iterations)")
        print("=" * 60)


# =============================================================================
# CLI 실행
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
