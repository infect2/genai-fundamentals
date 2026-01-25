"""
n8n Integration Test Configuration

pytest-asyncio 설정 및 테스트 픽스처
"""

import pytest


def pytest_configure(config):
    """pytest 설정 - asyncio 모드를 auto로 설정"""
    config.addinivalue_line(
        "markers", "asyncio: mark test as an async test"
    )
    config.addinivalue_line(
        "markers", "neo4j: mark test as requiring Neo4j connection"
    )


@pytest.fixture
def api_base_url():
    """API 기본 URL 픽스처"""
    import os
    return os.getenv("API_BASE_URL", "http://localhost:8000")
