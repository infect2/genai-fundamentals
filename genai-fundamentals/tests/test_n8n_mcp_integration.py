"""
n8n MCP Server Integration Test Suite

n8n 워크플로우와 연동하여 MCP 서버를 테스트합니다.

사용 방법:
1. 직접 테스트: pytest test_n8n_mcp_integration.py -v
2. Neo4j 없이 기본 테스트: pytest test_n8n_mcp_integration.py -v -k "not neo4j"
3. n8n 워크플로우 트리거: python test_n8n_mcp_integration.py --trigger-n8n

환경 설정:
- N8N_WEBHOOK_URL: n8n webhook URL (기본값: http://localhost:5678/webhook/mcp-test)
"""

import os
import sys
import json
import time
import asyncio
import subprocess
import pytest
import httpx
from typing import Optional
from dataclasses import dataclass, field


# =============================================================================
# Configuration
# =============================================================================

N8N_WEBHOOK_URL = os.getenv("N8N_WEBHOOK_URL", "http://localhost:5678/webhook/mcp-test")
MCP_TEST_SESSION_ID = "n8n-mcp-integration-test"


@dataclass
class MCPTestResult:
    """MCP 테스트 결과 데이터 클래스"""
    name: str
    passed: bool
    duration_ms: float
    message: str
    response: Optional[dict] = None


# =============================================================================
# MCP Test Scenarios
# =============================================================================

MCP_TEST_SCENARIOS = [
    {
        "name": "MCP Initialize",
        "type": "initialize",
        "description": "MCP 서버 초기화"
    },
    {
        "name": "MCP List Tools",
        "type": "tools_list",
        "expected_tools": ["agent_query", "reset_session", "list_sessions"],
        "description": "MCP 도구 목록 조회"
    },
    {
        "name": "MCP List Sessions",
        "type": "tool_call",
        "tool_name": "list_sessions",
        "arguments": {},
        "expected_fields": ["sessions", "count"],
        "description": "세션 목록 조회"
    },
    {
        "name": "MCP Reset Session (Not Found)",
        "type": "tool_call",
        "tool_name": "reset_session",
        "arguments": {"session_id": "nonexistent-session-12345"},
        "expected_contains": "not found",
        "description": "존재하지 않는 세션 리셋"
    },
]

# Neo4j 필요 테스트 시나리오 (Agent-Only)
MCP_NEO4J_TEST_SCENARIOS = [
    {
        "name": "MCP Agent Query: Actors in Matrix",
        "type": "tool_call",
        "tool_name": "agent_query",
        "arguments": {
            "query": "Which actors appeared in The Matrix?",
            "session_id": MCP_TEST_SESSION_ID
        },
        "expected_fields": ["answer", "thoughts", "iterations"],
        "description": "영화 배우 조회 쿼리 (Agent)"
    },
    {
        "name": "MCP Agent Query: Tom Hanks Movies",
        "type": "tool_call",
        "tool_name": "agent_query",
        "arguments": {
            "query": "What movies did Tom Hanks star in?",
            "session_id": MCP_TEST_SESSION_ID
        },
        "expected_fields": ["answer", "thoughts", "iterations"],
        "description": "배우별 출연 영화 조회 (Agent)"
    },
    {
        "name": "MCP Agent Query: Movie Director",
        "type": "tool_call",
        "tool_name": "agent_query",
        "arguments": {
            "query": "Who directed The Godfather?",
            "session_id": MCP_TEST_SESSION_ID
        },
        "expected_fields": ["answer", "thoughts", "iterations"],
        "description": "영화 감독 조회 (Agent)"
    },
    {
        "name": "MCP Reset Test Session",
        "type": "tool_call",
        "tool_name": "reset_session",
        "arguments": {"session_id": MCP_TEST_SESSION_ID},
        "expected_contains": "reset",
        "description": "테스트 세션 리셋"
    },
]


# =============================================================================
# MCP Test Client
# =============================================================================

class MCPTestClient:
    """MCP 서버 테스트 클라이언트"""

    def __init__(self):
        self.process: Optional[subprocess.Popen] = None
        self.request_id = 0

    def start(self):
        """MCP 서버 프로세스 시작"""
        env = {**os.environ, "PYTHONPATH": os.getcwd()}
        self.process = subprocess.Popen(
            [sys.executable, "-m", "genai-fundamentals.api.mcp_server"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            env=env
        )
        self.request_id = 0

    def stop(self):
        """MCP 서버 프로세스 종료"""
        if self.process:
            try:
                self.process.stdin.close()
                self.process.terminate()
                self.process.wait(timeout=5)
            except:
                self.process.kill()
            self.process = None

    def _next_id(self) -> int:
        self.request_id += 1
        return self.request_id

    def _send(self, request: dict):
        """요청 전송"""
        self.process.stdin.write(json.dumps(request) + "\n")
        self.process.stdin.flush()

    def _read_response(self, timeout: float = 120) -> Optional[dict]:
        """응답 읽기"""
        import select
        start = time.time()
        while time.time() - start < timeout:
            line = self.process.stdout.readline()
            if line:
                try:
                    return json.loads(line)
                except json.JSONDecodeError:
                    continue
            time.sleep(0.05)
        return None

    def initialize(self) -> dict:
        """MCP 초기화"""
        req_id = self._next_id()
        self._send({
            "jsonrpc": "2.0",
            "method": "initialize",
            "id": req_id,
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "n8n-test", "version": "1.0.0"}
            }
        })
        response = self._read_response(timeout=10)

        # Send initialized notification
        self._send({
            "jsonrpc": "2.0",
            "method": "notifications/initialized"
        })

        return response

    def list_tools(self) -> dict:
        """도구 목록 조회"""
        req_id = self._next_id()
        self._send({
            "jsonrpc": "2.0",
            "method": "tools/list",
            "id": req_id,
            "params": {}
        })
        return self._read_response(timeout=10)

    def call_tool(self, name: str, arguments: dict, timeout: float = 120) -> dict:
        """도구 호출"""
        req_id = self._next_id()
        self._send({
            "jsonrpc": "2.0",
            "method": "tools/call",
            "id": req_id,
            "params": {
                "name": name,
                "arguments": arguments
            }
        })
        return self._read_response(timeout=timeout)


# =============================================================================
# MCP Test Runner
# =============================================================================

class MCPIntegrationTestRunner:
    """MCP 통합 테스트 러너"""

    def __init__(self):
        self.client = MCPTestClient()
        self.results: list[MCPTestResult] = []

    def run_test(self, scenario: dict) -> MCPTestResult:
        """단일 테스트 시나리오 실행"""
        start_time = time.time()

        try:
            if scenario["type"] == "initialize":
                response = self.client.initialize()
                duration_ms = (time.time() - start_time) * 1000

                if response and "result" in response:
                    server_info = response["result"].get("serverInfo", {})
                    return MCPTestResult(
                        name=scenario["name"],
                        passed=True,
                        duration_ms=duration_ms,
                        message=f"Server: {server_info.get('name', 'unknown')}",
                        response=response
                    )
                else:
                    return MCPTestResult(
                        name=scenario["name"],
                        passed=False,
                        duration_ms=duration_ms,
                        message="Initialize failed",
                        response=response
                    )

            elif scenario["type"] == "tools_list":
                response = self.client.list_tools()
                duration_ms = (time.time() - start_time) * 1000

                if response and "result" in response:
                    tools = [t["name"] for t in response["result"].get("tools", [])]
                    expected = scenario.get("expected_tools", [])
                    missing = [t for t in expected if t not in tools]

                    if missing:
                        return MCPTestResult(
                            name=scenario["name"],
                            passed=False,
                            duration_ms=duration_ms,
                            message=f"Missing tools: {missing}",
                            response=response
                        )

                    return MCPTestResult(
                        name=scenario["name"],
                        passed=True,
                        duration_ms=duration_ms,
                        message=f"Tools: {tools}",
                        response=response
                    )
                else:
                    return MCPTestResult(
                        name=scenario["name"],
                        passed=False,
                        duration_ms=duration_ms,
                        message="List tools failed",
                        response=response
                    )

            elif scenario["type"] == "tool_call":
                response = self.client.call_tool(
                    scenario["tool_name"],
                    scenario["arguments"],
                    timeout=120
                )
                duration_ms = (time.time() - start_time) * 1000

                if response and "result" in response:
                    content = response["result"].get("content", [])
                    if content:
                        text = content[0].get("text", "")

                        # expected_contains 검증
                        if "expected_contains" in scenario:
                            if scenario["expected_contains"].lower() in text.lower():
                                return MCPTestResult(
                                    name=scenario["name"],
                                    passed=True,
                                    duration_ms=duration_ms,
                                    message="OK",
                                    response={"text": text}
                                )
                            else:
                                return MCPTestResult(
                                    name=scenario["name"],
                                    passed=False,
                                    duration_ms=duration_ms,
                                    message=f"Expected '{scenario['expected_contains']}' not found",
                                    response={"text": text}
                                )

                        # expected_fields 검증 (JSON 응답)
                        if "expected_fields" in scenario:
                            try:
                                data = json.loads(text)
                                missing = [f for f in scenario["expected_fields"] if f not in data]
                                if missing:
                                    return MCPTestResult(
                                        name=scenario["name"],
                                        passed=False,
                                        duration_ms=duration_ms,
                                        message=f"Missing fields: {missing}",
                                        response=data
                                    )
                                return MCPTestResult(
                                    name=scenario["name"],
                                    passed=True,
                                    duration_ms=duration_ms,
                                    message="OK",
                                    response=data
                                )
                            except json.JSONDecodeError:
                                return MCPTestResult(
                                    name=scenario["name"],
                                    passed=False,
                                    duration_ms=duration_ms,
                                    message="Invalid JSON response",
                                    response={"text": text}
                                )

                        return MCPTestResult(
                            name=scenario["name"],
                            passed=True,
                            duration_ms=duration_ms,
                            message="OK",
                            response={"text": text[:200]}
                        )

                elif response and "error" in response:
                    return MCPTestResult(
                        name=scenario["name"],
                        passed=False,
                        duration_ms=duration_ms,
                        message=f"Error: {response['error']}",
                        response=response
                    )

                return MCPTestResult(
                    name=scenario["name"],
                    passed=False,
                    duration_ms=duration_ms,
                    message="No response",
                    response=response
                )

        except Exception as e:
            return MCPTestResult(
                name=scenario["name"],
                passed=False,
                duration_ms=(time.time() - start_time) * 1000,
                message=f"Exception: {str(e)}"
            )

    def run_all_tests(self, include_neo4j: bool = False) -> list[MCPTestResult]:
        """모든 테스트 실행"""
        self.results = []
        scenarios = MCP_TEST_SCENARIOS.copy()

        if include_neo4j:
            scenarios.extend(MCP_NEO4J_TEST_SCENARIOS)

        self.client.start()

        try:
            for scenario in scenarios:
                result = self.run_test(scenario)
                self.results.append(result)
                status = "PASS" if result.passed else "FAIL"
                print(f"[{status}] {result.name} ({result.duration_ms:.0f}ms) - {result.message}")
        finally:
            self.client.stop()

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
        """n8n webhook 리포트 생성"""
        summary = self.get_summary()

        return {
            "test_suite": "MCP Server Integration Test",
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
# n8n Webhook
# =============================================================================

async def send_report_to_n8n(report: dict, webhook_url: str = N8N_WEBHOOK_URL):
    """테스트 결과를 n8n webhook으로 전송"""
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(webhook_url, json=report)
            print(f"\nn8n webhook response: {response.status_code}")
            return response.json() if response.status_code == 200 else response.text
    except Exception as e:
        print(f"\nFailed to send report to n8n: {e}")
        return None


# =============================================================================
# Pytest Test Cases
# =============================================================================

@pytest.fixture
def mcp_runner():
    """MCP 테스트 러너 fixture"""
    runner = MCPIntegrationTestRunner()
    yield runner
    runner.client.stop()


class TestMCPBasic:
    """MCP 기본 테스트 (Neo4j 불필요)"""

    def test_mcp_initialize(self, mcp_runner):
        """MCP 서버 초기화 테스트"""
        mcp_runner.client.start()
        result = mcp_runner.run_test(MCP_TEST_SCENARIOS[0])
        mcp_runner.client.stop()
        assert result.passed, result.message

    def test_mcp_list_tools(self, mcp_runner):
        """MCP 도구 목록 테스트"""
        mcp_runner.client.start()
        mcp_runner.run_test(MCP_TEST_SCENARIOS[0])  # Initialize first
        result = mcp_runner.run_test(MCP_TEST_SCENARIOS[1])
        mcp_runner.client.stop()
        assert result.passed, result.message

    def test_mcp_list_sessions(self, mcp_runner):
        """MCP 세션 목록 테스트"""
        mcp_runner.client.start()
        mcp_runner.run_test(MCP_TEST_SCENARIOS[0])  # Initialize
        result = mcp_runner.run_test(MCP_TEST_SCENARIOS[2])
        mcp_runner.client.stop()
        assert result.passed, result.message

    def test_mcp_reset_session_not_found(self, mcp_runner):
        """MCP 존재하지 않는 세션 리셋 테스트"""
        mcp_runner.client.start()
        mcp_runner.run_test(MCP_TEST_SCENARIOS[0])  # Initialize
        result = mcp_runner.run_test(MCP_TEST_SCENARIOS[3])
        mcp_runner.client.stop()
        assert result.passed, result.message


@pytest.mark.neo4j
class TestMCPWithNeo4j:
    """MCP Neo4j 연동 테스트"""

    def test_mcp_query_actors(self, mcp_runner):
        """MCP 배우 조회 쿼리 테스트"""
        mcp_runner.client.start()
        mcp_runner.run_test(MCP_TEST_SCENARIOS[0])  # Initialize
        result = mcp_runner.run_test(MCP_NEO4J_TEST_SCENARIOS[0])
        mcp_runner.client.stop()
        assert result.passed, result.message

    def test_mcp_query_movies(self, mcp_runner):
        """MCP 영화 조회 쿼리 테스트"""
        mcp_runner.client.start()
        mcp_runner.run_test(MCP_TEST_SCENARIOS[0])  # Initialize
        result = mcp_runner.run_test(MCP_NEO4J_TEST_SCENARIOS[1])
        mcp_runner.client.stop()
        assert result.passed, result.message

    def test_mcp_query_director(self, mcp_runner):
        """MCP 감독 조회 쿼리 테스트"""
        mcp_runner.client.start()
        mcp_runner.run_test(MCP_TEST_SCENARIOS[0])  # Initialize
        result = mcp_runner.run_test(MCP_NEO4J_TEST_SCENARIOS[2])
        mcp_runner.client.stop()
        assert result.passed, result.message


def test_mcp_full_integration():
    """MCP 전체 통합 테스트 (Neo4j 없이)"""
    runner = MCPIntegrationTestRunner()
    runner.run_all_tests(include_neo4j=False)

    summary = runner.get_summary()
    print(f"\n{'='*60}")
    print(f"MCP Test Summary: {summary['passed']}/{summary['total']} passed ({summary['pass_rate']})")
    print(f"Total Duration: {summary['duration_ms']:.0f}ms")
    print(f"{'='*60}")

    assert summary["failed"] == 0, f"{summary['failed']} tests failed"


@pytest.mark.neo4j
def test_mcp_full_integration_with_neo4j():
    """MCP 전체 통합 테스트 (Neo4j 포함)"""
    runner = MCPIntegrationTestRunner()
    runner.run_all_tests(include_neo4j=True)

    summary = runner.get_summary()
    print(f"\n{'='*60}")
    print(f"MCP Test Summary: {summary['passed']}/{summary['total']} passed ({summary['pass_rate']})")
    print(f"Total Duration: {summary['duration_ms']:.0f}ms")
    print(f"{'='*60}")

    assert summary["failed"] == 0, f"{summary['failed']} tests failed"


# =============================================================================
# CLI Entry Point
# =============================================================================

def main():
    """CLI 메인 함수"""
    import argparse

    parser = argparse.ArgumentParser(description="MCP Server n8n Integration Test Suite")
    parser.add_argument("--include-neo4j", action="store_true", help="Include Neo4j tests")
    parser.add_argument("--trigger-n8n", action="store_true", help="Send results to n8n webhook")
    parser.add_argument("--n8n-url", default=N8N_WEBHOOK_URL, help="n8n webhook URL")
    parser.add_argument("--json", action="store_true", help="Output results as JSON")
    args = parser.parse_args()

    print(f"MCP Server Integration Test Suite")
    print(f"{'='*60}\n")

    runner = MCPIntegrationTestRunner()
    runner.run_all_tests(include_neo4j=args.include_neo4j)

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
        asyncio.run(send_report_to_n8n(report, args.n8n_url))

    return 0 if summary["failed"] == 0 else 1


if __name__ == "__main__":
    exit(main())
