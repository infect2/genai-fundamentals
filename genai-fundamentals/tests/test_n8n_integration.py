"""
n8n Integration Test Suite

n8n 워크플로우와 연동하여 GraphRAG API를 테스트합니다.

사용 방법:
1. 직접 API 테스트: pytest test_n8n_integration.py -v
2. n8n 워크플로우 트리거: python test_n8n_integration.py --trigger-n8n

환경 설정:
- API_BASE_URL: GraphRAG API 서버 URL (기본값: http://localhost:8000)
- N8N_WEBHOOK_URL: n8n webhook URL (n8n 워크플로우에서 설정)
"""

import os
import json
import time
import asyncio
import pytest
import httpx
from typing import Optional
from dataclasses import dataclass


# =============================================================================
# Configuration
# =============================================================================

API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
N8N_WEBHOOK_URL = os.getenv("N8N_WEBHOOK_URL", "http://localhost:5678/webhook/graphrag-test")
TEST_SESSION_ID = "n8n-integration-test"


@dataclass
class IntegrationTestResult:
    """테스트 결과 데이터 클래스"""
    name: str
    passed: bool
    duration_ms: float
    message: str
    response: Optional[dict] = None


# =============================================================================
# Test Scenarios
# =============================================================================

TEST_SCENARIOS = [
    {
        "name": "Health Check",
        "method": "GET",
        "endpoint": "/",
        "body": None,
        "expected_fields": ["message", "version"],
        "description": "서버 상태 확인"
    },
    {
        "name": "Query: Actors in Matrix",
        "method": "POST",
        "endpoint": "/query",
        "body": {
            "query": "Which actors appeared in The Matrix?",
            "session_id": TEST_SESSION_ID,
            "reset_context": True,
            "stream": False
        },
        "expected_fields": ["answer", "cypher", "context"],
        "description": "영화 배우 조회 쿼리"
    },
    {
        "name": "Query: Keanu Reeves Movies",
        "method": "POST",
        "endpoint": "/query",
        "body": {
            "query": "What movies did Keanu Reeves act in?",
            "session_id": TEST_SESSION_ID,
            "reset_context": False,
            "stream": False
        },
        "expected_fields": ["answer", "cypher", "context"],
        "description": "배우별 출연 영화 조회"
    },
    {
        "name": "Query: Movie Directors",
        "method": "POST",
        "endpoint": "/query",
        "body": {
            "query": "Who directed The Godfather?",
            "session_id": TEST_SESSION_ID,
            "reset_context": False,
            "stream": False
        },
        "expected_fields": ["answer", "cypher", "context"],
        "description": "영화 감독 조회"
    },
    {
        "name": "Query: Genre Search",
        "method": "POST",
        "endpoint": "/query",
        "body": {
            "query": "Show me action movies",
            "session_id": TEST_SESSION_ID,
            "reset_context": False,
            "stream": False
        },
        "expected_fields": ["answer", "cypher", "context"],
        "description": "장르별 영화 검색"
    },
    {
        "name": "List Sessions",
        "method": "GET",
        "endpoint": "/sessions",
        "body": None,
        "expected_fields": ["sessions"],
        "description": "활성 세션 목록 조회"
    },
    {
        "name": "Reset Session",
        "method": "POST",
        "endpoint": f"/reset/{TEST_SESSION_ID}",
        "body": None,
        "expected_fields": ["message"],
        "description": "테스트 세션 리셋"
    }
]


# =============================================================================
# Test Runner
# =============================================================================

class N8NIntegrationTestRunner:
    """n8n 통합 테스트 러너"""

    def __init__(self, base_url: str = API_BASE_URL):
        self.base_url = base_url.rstrip("/")
        self.results: list[IntegrationTestResult] = []

    async def run_test(self, scenario: dict) -> IntegrationTestResult:
        """단일 테스트 시나리오 실행"""
        start_time = time.time()

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                url = f"{self.base_url}{scenario['endpoint']}"

                if scenario["method"] == "GET":
                    response = await client.get(url)
                elif scenario["method"] == "POST":
                    if scenario["body"]:
                        response = await client.post(url, json=scenario["body"])
                    else:
                        response = await client.post(url)
                else:
                    raise ValueError(f"Unsupported method: {scenario['method']}")

                duration_ms = (time.time() - start_time) * 1000
                response_data = response.json()

                # 응답 검증
                if response.status_code != 200:
                    return IntegrationTestResult(
                        name=scenario["name"],
                        passed=False,
                        duration_ms=duration_ms,
                        message=f"HTTP {response.status_code}: {response.text}",
                        response=response_data
                    )

                # 필수 필드 검증
                missing_fields = []
                for field in scenario["expected_fields"]:
                    if field not in response_data:
                        missing_fields.append(field)

                if missing_fields:
                    return IntegrationTestResult(
                        name=scenario["name"],
                        passed=False,
                        duration_ms=duration_ms,
                        message=f"Missing fields: {missing_fields}",
                        response=response_data
                    )

                return IntegrationTestResult(
                    name=scenario["name"],
                    passed=True,
                    duration_ms=duration_ms,
                    message="OK",
                    response=response_data
                )

        except httpx.ConnectError:
            return IntegrationTestResult(
                name=scenario["name"],
                passed=False,
                duration_ms=(time.time() - start_time) * 1000,
                message=f"Connection failed: {self.base_url}"
            )
        except Exception as e:
            return IntegrationTestResult(
                name=scenario["name"],
                passed=False,
                duration_ms=(time.time() - start_time) * 1000,
                message=f"Error: {str(e)}"
            )

    async def run_all_tests(self) -> list[IntegrationTestResult]:
        """모든 테스트 시나리오 실행"""
        self.results = []

        for scenario in TEST_SCENARIOS:
            result = await self.run_test(scenario)
            self.results.append(result)
            status = "PASS" if result.passed else "FAIL"
            print(f"[{status}] {result.name} ({result.duration_ms:.0f}ms) - {result.message}")

        return self.results

    def get_summary(self) -> dict:
        """테스트 결과 요약"""
        passed = sum(1 for r in self.results if r.passed)
        failed = sum(1 for r in self.results if not r.passed)
        total_duration = sum(r.duration_ms for r in self.results)

        return {
            "total": len(self.results),
            "passed": passed,
            "failed": failed,
            "duration_ms": total_duration,
            "pass_rate": f"{(passed / len(self.results) * 100):.1f}%" if self.results else "N/A"
        }

    def generate_n8n_report(self) -> dict:
        """n8n webhook으로 전송할 리포트 생성"""
        summary = self.get_summary()

        return {
            "test_suite": "GraphRAG API Integration Test",
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "summary": summary,
            "results": [
                {
                    "name": r.name,
                    "passed": r.passed,
                    "duration_ms": r.duration_ms,
                    "message": r.message
                }
                for r in self.results
            ]
        }


# =============================================================================
# n8n Webhook Trigger
# =============================================================================

async def trigger_n8n_webhook(webhook_url: str, payload: dict) -> dict:
    """n8n webhook 트리거"""
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(webhook_url, json=payload)
        return {
            "status_code": response.status_code,
            "response": response.json() if response.status_code == 200 else response.text
        }


async def send_test_report_to_n8n(report: dict, webhook_url: str = N8N_WEBHOOK_URL):
    """테스트 결과를 n8n webhook으로 전송"""
    try:
        result = await trigger_n8n_webhook(webhook_url, report)
        print(f"\nn8n webhook response: {result}")
        return result
    except Exception as e:
        print(f"\nFailed to send report to n8n: {e}")
        return None


# =============================================================================
# Pytest Test Cases
# =============================================================================

@pytest.fixture
def runner():
    """테스트 러너 fixture"""
    return N8NIntegrationTestRunner(API_BASE_URL)


@pytest.mark.asyncio
async def test_health_check(runner):
    """서버 헬스 체크 테스트"""
    scenario = TEST_SCENARIOS[0]
    result = await runner.run_test(scenario)
    assert result.passed, result.message


@pytest.mark.asyncio
async def test_query_actors(runner):
    """배우 조회 쿼리 테스트"""
    scenario = TEST_SCENARIOS[1]
    result = await runner.run_test(scenario)
    assert result.passed, result.message
    assert "answer" in result.response


@pytest.mark.asyncio
async def test_query_movies(runner):
    """영화 조회 쿼리 테스트"""
    scenario = TEST_SCENARIOS[2]
    result = await runner.run_test(scenario)
    assert result.passed, result.message


@pytest.mark.asyncio
async def test_query_directors(runner):
    """감독 조회 쿼리 테스트"""
    scenario = TEST_SCENARIOS[3]
    result = await runner.run_test(scenario)
    assert result.passed, result.message


@pytest.mark.asyncio
async def test_query_genre(runner):
    """장르별 영화 검색 테스트"""
    scenario = TEST_SCENARIOS[4]
    result = await runner.run_test(scenario)
    assert result.passed, result.message


@pytest.mark.asyncio
async def test_list_sessions(runner):
    """세션 목록 조회 테스트"""
    scenario = TEST_SCENARIOS[5]
    result = await runner.run_test(scenario)
    assert result.passed, result.message


@pytest.mark.asyncio
async def test_reset_session(runner):
    """세션 리셋 테스트"""
    scenario = TEST_SCENARIOS[6]
    result = await runner.run_test(scenario)
    assert result.passed, result.message


@pytest.mark.asyncio
async def test_full_integration():
    """전체 통합 테스트"""
    runner = N8NIntegrationTestRunner(API_BASE_URL)
    results = await runner.run_all_tests()

    summary = runner.get_summary()
    print(f"\n{'='*60}")
    print(f"Test Summary: {summary['passed']}/{summary['total']} passed ({summary['pass_rate']})")
    print(f"Total Duration: {summary['duration_ms']:.0f}ms")
    print(f"{'='*60}")

    assert summary["failed"] == 0, f"{summary['failed']} tests failed"


# =============================================================================
# CLI Entry Point
# =============================================================================

async def main():
    """CLI 메인 함수"""
    import argparse

    parser = argparse.ArgumentParser(description="n8n Integration Test Suite")
    parser.add_argument("--api-url", default=API_BASE_URL, help="GraphRAG API base URL")
    parser.add_argument("--trigger-n8n", action="store_true", help="Send results to n8n webhook")
    parser.add_argument("--n8n-url", default=N8N_WEBHOOK_URL, help="n8n webhook URL")
    parser.add_argument("--json", action="store_true", help="Output results as JSON")
    args = parser.parse_args()

    print(f"GraphRAG API Integration Test Suite")
    print(f"API URL: {args.api_url}")
    print(f"{'='*60}\n")

    runner = N8NIntegrationTestRunner(args.api_url)
    await runner.run_all_tests()

    summary = runner.get_summary()
    report = runner.generate_n8n_report()

    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        print(f"\n{'='*60}")
        print(f"Summary: {summary['passed']}/{summary['total']} passed ({summary['pass_rate']})")
        print(f"Total Duration: {summary['duration_ms']:.0f}ms")
        print(f"{'='*60}")

    if args.trigger_n8n:
        print(f"\nSending report to n8n: {args.n8n_url}")
        await send_test_report_to_n8n(report, args.n8n_url)

    return 0 if summary["failed"] == 0 else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)
