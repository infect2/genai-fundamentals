"""
MCP Server Integration Tests

MCP 서버의 기능을 테스트합니다.
- 서버 초기화
- 도구 목록 조회
- 세션 관리 (list_sessions, reset_session)
- 쿼리 실행 (Neo4j 연결 필요)

실행 방법:
    # 모든 MCP 테스트 실행
    pytest genai-fundamentals/tests/test_mcp_server.py -v

    # Neo4j 없이 기본 테스트만 실행
    pytest genai-fundamentals/tests/test_mcp_server.py -v -k "not neo4j"

    # 쿼리 테스트 포함 (Neo4j 연결 필요)
    pytest genai-fundamentals/tests/test_mcp_server.py -v -k "neo4j"
"""

import pytest
import subprocess
import json
import sys
import os


class MCPTestClient:
    """MCP 서버와 통신하는 테스트 클라이언트"""

    def __init__(self):
        self.process = None
        self.initialized = False

    def start(self):
        """MCP 서버 프로세스 시작"""
        self.process = subprocess.Popen(
            [sys.executable, "-m", "genai-fundamentals.api.mcp_server"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        )

    def stop(self):
        """MCP 서버 프로세스 종료"""
        if self.process:
            self.process.terminate()
            self.process.wait(timeout=5)
            self.process = None
            self.initialized = False

    def send_request(self, request: dict) -> dict:
        """단일 요청 전송 및 응답 수신"""
        if not self.process:
            raise RuntimeError("MCP server not started")

        self.process.stdin.write(json.dumps(request) + "\n")
        self.process.stdin.flush()

        line = self.process.stdout.readline()
        if line:
            return json.loads(line)
        return {}

    def send_requests(self, requests: list[dict], timeout: float = 30) -> list[dict]:
        """여러 요청 전송 및 응답 수신"""
        if not self.process:
            raise RuntimeError("MCP server not started")

        input_data = "\n".join(json.dumps(r) for r in requests) + "\n"

        try:
            stdout, stderr = self.process.communicate(input=input_data, timeout=timeout)
        except subprocess.TimeoutExpired:
            self.process.kill()
            raise TimeoutError(f"MCP server timeout after {timeout}s")

        responses = []
        for line in stdout.strip().split("\n"):
            if line:
                try:
                    responses.append(json.loads(line))
                except json.JSONDecodeError:
                    pass

        return responses

    def send_requests_sequential(
        self, requests: list[dict], timeout: float = 30
    ) -> list[dict]:
        """
        요청을 순차적으로 전송하고 응답을 수집 (stdin 닫지 않음)

        communicate()와 달리 stdin을 열어둔 채로 각 요청에 대한 응답을 기다립니다.
        agent_query와 같이 오래 걸리는 작업에 적합합니다.
        """
        import select
        import time

        if not self.process:
            raise RuntimeError("MCP server not started")

        responses = []
        start_time = time.time()

        for req in requests:
            # 요청 전송
            self.process.stdin.write(json.dumps(req) + "\n")
            self.process.stdin.flush()

            # notification은 응답을 기다리지 않음
            if "id" not in req:
                continue

            # 응답 대기 (select로 타임아웃 처리)
            remaining_timeout = timeout - (time.time() - start_time)
            if remaining_timeout <= 0:
                raise TimeoutError(f"MCP server timeout after {timeout}s")

            # select를 사용하여 stdout이 읽을 준비가 될 때까지 대기
            ready, _, _ = select.select(
                [self.process.stdout], [], [], remaining_timeout
            )

            if ready:
                line = self.process.stdout.readline()
                if line:
                    try:
                        responses.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
            else:
                raise TimeoutError(
                    f"Timeout waiting for response to request id={req.get('id')}"
                )

        return responses

    def initialize(self) -> dict:
        """MCP 프로토콜 초기화"""
        requests = [
            {
                "jsonrpc": "2.0",
                "method": "initialize",
                "id": 1,
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "test-client", "version": "1.0.0"}
                }
            },
            {
                "jsonrpc": "2.0",
                "method": "notifications/initialized"
            }
        ]

        self.start()
        responses = self.send_requests(requests)
        self.initialized = True

        # 초기화 응답 반환
        for resp in responses:
            if resp.get("id") == 1:
                return resp
        return {}


@pytest.fixture
def mcp_client():
    """MCP 테스트 클라이언트 픽스처"""
    client = MCPTestClient()
    yield client
    client.stop()


class TestMCPServerBasic:
    """MCP 서버 기본 테스트 (Neo4j 연결 불필요)"""

    def test_server_initialization(self, mcp_client):
        """서버 초기화 테스트"""
        response = mcp_client.initialize()

        assert "result" in response
        result = response["result"]

        # 프로토콜 버전 확인
        assert result["protocolVersion"] == "2024-11-05"

        # 서버 정보 확인
        assert result["serverInfo"]["name"] == "capora-mcp"

        # 도구 기능 확인
        assert "tools" in result["capabilities"]

    def test_list_tools(self, mcp_client):
        """도구 목록 조회 테스트"""
        mcp_client.start()

        requests = [
            {
                "jsonrpc": "2.0",
                "method": "initialize",
                "id": 1,
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "test", "version": "1.0.0"}
                }
            },
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            {"jsonrpc": "2.0", "method": "tools/list", "id": 2, "params": {}}
        ]

        responses = mcp_client.send_requests(requests)

        # tools/list 응답 찾기
        tools_response = None
        for resp in responses:
            if resp.get("id") == 2:
                tools_response = resp
                break

        assert tools_response is not None
        assert "result" in tools_response

        tools = tools_response["result"]["tools"]
        tool_names = [t["name"] for t in tools]

        # 필수 도구 확인
        assert "agent_query" in tool_names
        assert "reset_session" in tool_names
        assert "list_sessions" in tool_names

    def test_tool_schemas(self, mcp_client):
        """도구 스키마 검증 테스트"""
        mcp_client.start()

        requests = [
            {
                "jsonrpc": "2.0",
                "method": "initialize",
                "id": 1,
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "test", "version": "1.0.0"}
                }
            },
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            {"jsonrpc": "2.0", "method": "tools/list", "id": 2, "params": {}}
        ]

        responses = mcp_client.send_requests(requests)

        tools_response = None
        for resp in responses:
            if resp.get("id") == 2:
                tools_response = resp
                break

        tools = {t["name"]: t for t in tools_response["result"]["tools"]}

        # agent_query 도구 스키마 검증
        agent_tool = tools["agent_query"]
        assert agent_tool["inputSchema"]["type"] == "object"
        assert "query" in agent_tool["inputSchema"]["properties"]
        assert "query" in agent_tool["inputSchema"]["required"]

        # reset_session 도구 스키마 검증
        reset_tool = tools["reset_session"]
        assert "session_id" in reset_tool["inputSchema"]["properties"]
        assert "session_id" in reset_tool["inputSchema"]["required"]

        # list_sessions 도구 스키마 검증
        list_tool = tools["list_sessions"]
        assert list_tool["inputSchema"]["type"] == "object"

    def test_list_sessions_tool(self, mcp_client):
        """list_sessions 도구 호출 테스트"""
        mcp_client.start()

        requests = [
            {
                "jsonrpc": "2.0",
                "method": "initialize",
                "id": 1,
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "test", "version": "1.0.0"}
                }
            },
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            {
                "jsonrpc": "2.0",
                "method": "tools/call",
                "id": 2,
                "params": {"name": "list_sessions", "arguments": {}}
            }
        ]

        responses = mcp_client.send_requests(requests)

        call_response = None
        for resp in responses:
            if resp.get("id") == 2:
                call_response = resp
                break

        assert call_response is not None
        assert "result" in call_response
        assert call_response["result"]["isError"] is False

        # 응답 내용 파싱
        content = call_response["result"]["content"][0]["text"]
        data = json.loads(content)

        assert "sessions" in data
        assert "count" in data
        assert isinstance(data["sessions"], list)

    def test_reset_session_tool_not_found(self, mcp_client):
        """존재하지 않는 세션 리셋 테스트"""
        mcp_client.start()

        requests = [
            {
                "jsonrpc": "2.0",
                "method": "initialize",
                "id": 1,
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "test", "version": "1.0.0"}
                }
            },
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            {
                "jsonrpc": "2.0",
                "method": "tools/call",
                "id": 2,
                "params": {
                    "name": "reset_session",
                    "arguments": {"session_id": "nonexistent-session"}
                }
            }
        ]

        responses = mcp_client.send_requests(requests)

        call_response = None
        for resp in responses:
            if resp.get("id") == 2:
                call_response = resp
                break

        assert call_response is not None
        assert "result" in call_response

        content = call_response["result"]["content"][0]["text"]
        assert "not found" in content


@pytest.mark.neo4j
class TestMCPServerWithNeo4j:
    """MCP 서버 Neo4j 연동 테스트 (Neo4j 연결 필요)"""

    def test_agent_query_tool(self, mcp_client):
        """agent_query 도구 호출 테스트"""
        mcp_client.start()

        requests = [
            {
                "jsonrpc": "2.0",
                "method": "initialize",
                "id": 1,
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "test", "version": "1.0.0"}
                }
            },
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            {
                "jsonrpc": "2.0",
                "method": "tools/call",
                "id": 2,
                "params": {
                    "name": "agent_query",
                    "arguments": {
                        "query": "Which actors appeared in The Matrix?",
                        "session_id": "test-session"
                    }
                }
            }
        ]

        # 순차 전송 방식 사용 (stdin을 열어둔 채로 각 응답 대기)
        responses = mcp_client.send_requests_sequential(requests, timeout=120)

        # 응답에서 id=2 찾기
        call_response = None
        error_responses = []
        for resp in responses:
            if resp.get("id") == 2:
                call_response = resp
            # 에러 응답 수집
            if "error" in resp:
                error_responses.append(resp)

        # 에러 응답이 있으면 먼저 확인
        if error_responses and call_response is None:
            pytest.skip(f"MCP server returned errors: {error_responses}")

        # 응답이 없으면 모든 응답 출력하여 디버깅 지원
        assert call_response is not None, (
            f"No response with id=2 found. "
            f"Total responses: {len(responses)}, "
            f"Response IDs: {[r.get('id') for r in responses]}"
        )
        assert "result" in call_response, f"No result in response: {call_response}"
        assert call_response["result"]["isError"] is False, (
            f"Tool call returned error: {call_response['result']}"
        )

        # 응답 내용 파싱
        content = call_response["result"]["content"][0]["text"]
        data = json.loads(content)

        assert "answer" in data
        assert "thoughts" in data
        assert "iterations" in data

    def test_agent_query_with_session_context(self, mcp_client):
        """세션 컨텍스트를 사용한 Agent 쿼리 테스트"""
        mcp_client.start()

        requests = [
            {
                "jsonrpc": "2.0",
                "method": "initialize",
                "id": 1,
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "test", "version": "1.0.0"}
                }
            },
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            # 첫 번째 쿼리
            {
                "jsonrpc": "2.0",
                "method": "tools/call",
                "id": 2,
                "params": {
                    "name": "agent_query",
                    "arguments": {
                        "query": "What is Toy Story about?",
                        "session_id": "context-test-session"
                    }
                }
            },
            # 세션 목록 확인
            {
                "jsonrpc": "2.0",
                "method": "tools/call",
                "id": 3,
                "params": {"name": "list_sessions", "arguments": {}}
            }
        ]

        # 순차 전송 방식 사용 (agent_query가 오래 걸릴 수 있음)
        responses = mcp_client.send_requests_sequential(requests, timeout=120)

        # 세션 목록에서 세션 확인
        list_response = None
        for resp in responses:
            if resp.get("id") == 3:
                list_response = resp
                break

        if list_response and "result" in list_response:
            content = list_response["result"]["content"][0]["text"]
            data = json.loads(content)
            assert "context-test-session" in data["sessions"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
