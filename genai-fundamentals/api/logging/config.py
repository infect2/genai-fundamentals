"""
Elasticsearch Client Configuration

환경변수 기반으로 Elasticsearch 클라이언트를 설정합니다.

환경변수:
- ES_LOGGING_ENABLED: 로깅 활성화 여부 (기본값: false)
- ES_HOST: Elasticsearch 호스트 (기본값: localhost)
- ES_PORT: Elasticsearch 포트 (기본값: 9200)
- ES_INDEX_PREFIX: 인덱스 접두사 (기본값: graphrag-logs)
- ES_API_KEY: API 키 (선택, 인증 필요 시)
"""

import os
import logging
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

# =============================================================================
# 환경변수 로드
# =============================================================================

ES_ENABLED: bool = os.getenv("ES_LOGGING_ENABLED", "false").lower() == "true"
ES_HOST: str = os.getenv("ES_HOST", "localhost")
ES_PORT: int = int(os.getenv("ES_PORT", "9200"))
ES_INDEX_PREFIX: str = os.getenv("ES_INDEX_PREFIX", "graphrag-logs")
ES_API_KEY: str = os.getenv("ES_API_KEY", "")

# =============================================================================
# Elasticsearch 클라이언트 싱글톤
# =============================================================================

_es_client = None


def get_es_client():
    """
    Elasticsearch 클라이언트 싱글톤 반환

    ES_LOGGING_ENABLED가 true일 때만 클라이언트를 생성합니다.
    연결 실패 시 None을 반환하고 경고를 로깅합니다.

    Returns:
        Elasticsearch 클라이언트 또는 None
    """
    global _es_client

    if not ES_ENABLED:
        return None

    if _es_client is None:
        try:
            from elasticsearch import Elasticsearch

            # API 키가 있으면 사용, 없으면 인증 없이 연결
            if ES_API_KEY:
                _es_client = Elasticsearch(
                    f"http://{ES_HOST}:{ES_PORT}",
                    api_key=ES_API_KEY
                )
            else:
                _es_client = Elasticsearch(
                    f"http://{ES_HOST}:{ES_PORT}"
                )

            # 연결 테스트
            if _es_client.ping():
                logger.info(f"Elasticsearch connected: {ES_HOST}:{ES_PORT}")
            else:
                logger.warning("Elasticsearch ping failed")
                _es_client = None

        except ImportError:
            logger.error("elasticsearch package not installed. Run: pip install elasticsearch")
            _es_client = None
        except Exception as e:
            logger.error(f"Elasticsearch connection failed: {e}")
            _es_client = None

    return _es_client


def get_index_name() -> str:
    """
    일별 인덱스명 생성

    인덱스명 형식: {prefix}-YYYY.MM.DD
    예: graphrag-logs-2024.01.25

    Returns:
        인덱스명 문자열
    """
    date_str = datetime.utcnow().strftime("%Y.%m.%d")
    return f"{ES_INDEX_PREFIX}-{date_str}"


def close_es_client():
    """
    Elasticsearch 클라이언트 종료

    서버 종료 시 호출하여 리소스를 정리합니다.
    """
    global _es_client

    if _es_client is not None:
        try:
            _es_client.close()
            logger.info("Elasticsearch client closed")
        except Exception as e:
            logger.error(f"Error closing Elasticsearch client: {e}")
        finally:
            _es_client = None
