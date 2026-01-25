"""
Query Cache Module

쿼리 결과 캐싱을 통한 성능 최적화.
동일하거나 유사한 쿼리에 대해 캐시된 결과를 반환합니다.

Features:
- LRU 캐시 기반 인메모리 캐싱
- TTL(Time-To-Live) 지원
- 쿼리 정규화를 통한 유사 쿼리 매칭
- 스키마 캐싱 (장기 TTL)
- 통계 및 모니터링
"""

import hashlib
import time
import threading
import re
from typing import Optional, Any, Dict, Tuple
from dataclasses import dataclass, field
from collections import OrderedDict
from functools import lru_cache
import logging

logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    """캐시 엔트리"""
    value: Any
    created_at: float
    ttl: float  # seconds
    hits: int = 0

    def is_expired(self) -> bool:
        """TTL 만료 여부 확인"""
        return time.time() - self.created_at > self.ttl


@dataclass
class CacheStats:
    """캐시 통계"""
    hits: int = 0
    misses: int = 0
    evictions: int = 0

    @property
    def hit_rate(self) -> float:
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0


class QueryCache:
    """
    쿼리 결과 캐시

    LRU 기반 인메모리 캐시로, TTL과 최대 크기를 지원합니다.
    쿼리 정규화를 통해 유사한 쿼리도 캐시 히트할 수 있습니다.

    Usage:
        cache = QueryCache(max_size=1000, default_ttl=300)

        # 캐시 조회
        result = cache.get(query, session_id)
        if result is None:
            result = execute_query(query)
            cache.set(query, session_id, result)
    """

    def __init__(
        self,
        max_size: int = 1000,
        default_ttl: float = 300,  # 5 minutes
        schema_ttl: float = 3600,  # 1 hour for schema
        enable_normalization: bool = True
    ):
        """
        Args:
            max_size: 최대 캐시 엔트리 수
            default_ttl: 기본 TTL (초)
            schema_ttl: 스키마 캐시 TTL (초)
            enable_normalization: 쿼리 정규화 활성화
        """
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._max_size = max_size
        self._default_ttl = default_ttl
        self._schema_ttl = schema_ttl
        self._enable_normalization = enable_normalization
        self._lock = threading.RLock()
        self._stats = CacheStats()

        # 스키마 캐시 (별도 관리)
        self._schema_cache: Optional[Tuple[str, float]] = None

    def _normalize_query(self, query: str) -> str:
        """
        쿼리 정규화

        공백, 대소문자, 숫자 등을 정규화하여 유사한 쿼리가
        동일한 캐시 키를 갖도록 합니다.
        """
        if not self._enable_normalization:
            return query

        # 소문자 변환
        normalized = query.lower().strip()

        # 연속 공백 제거
        normalized = re.sub(r'\s+', ' ', normalized)

        # 숫자를 플레이스홀더로 (유사 쿼리 매칭 향상)
        normalized = re.sub(r'\d+', '<N>', normalized)

        # 따옴표 통일
        normalized = normalized.replace('"', "'")

        # 일반적인 변형 패턴 통일
        # "보여줘", "알려줘", "찾아줘" 등을 통일
        normalized = re.sub(r'(보여|알려|찾아|조회해)\s*줘?', '보여줘', normalized)

        # "몇 개", "몇개" 등 통일
        normalized = re.sub(r'몇\s*개', '<N>개', normalized)

        # 조사 제거 (은/는, 이/가, 을/를, 의, 에, 에서, 으로, 로)
        # 조사를 제거하여 유사 쿼리 매칭 향상
        normalized = re.sub(r'([가-힣])(은|는|이|가|을|를|의|에서|에|으로|로)\s', r'\1 ', normalized)
        normalized = re.sub(r'([가-힣])(은|는|이|가|을|를|의|에서|에|으로|로)$', r'\1', normalized)

        # 의문사 제거 (뭐야, 뭐지, 무엇)
        normalized = re.sub(r'\s*(뭐야|뭐지|무엇인가요?|무엇이야)\??', '', normalized)

        # 마지막 물음표 제거
        normalized = normalized.rstrip('?')

        # 끝에 조사만 남은 경우 제거 (예: "종류는" → "종류")
        normalized = re.sub(r'(는|은|가|이)$', '', normalized)

        # 동사 없이 끝나는 쿼리에 기본 동사 추가 (정규화 목적)
        if not re.search(r'(보여줘|해줘|줘)$', normalized):
            normalized = normalized.rstrip() + ' 보여줘'

        return normalized

    def _make_key(self, query: str, session_id: str = "") -> str:
        """캐시 키 생성"""
        normalized = self._normalize_query(query)
        # 세션 ID는 컨텍스트 의존적 쿼리에만 사용
        # 일반 쿼리는 세션 무관하게 캐싱
        key_str = f"{normalized}"
        return hashlib.md5(key_str.encode()).hexdigest()

    def get(self, query: str, session_id: str = "") -> Optional[Any]:
        """
        캐시에서 결과 조회

        Args:
            query: 쿼리 문자열
            session_id: 세션 ID

        Returns:
            캐시된 결과 또는 None
        """
        key = self._make_key(query, session_id)

        with self._lock:
            entry = self._cache.get(key)

            if entry is None:
                self._stats.misses += 1
                return None

            if entry.is_expired():
                # 만료된 엔트리 제거
                del self._cache[key]
                self._stats.misses += 1
                self._stats.evictions += 1
                return None

            # 히트: LRU 업데이트 (최근 사용으로 이동)
            self._cache.move_to_end(key)
            entry.hits += 1
            self._stats.hits += 1

            logger.debug(f"Cache HIT: {query[:50]}... (hits={entry.hits})")
            return entry.value

    def set(
        self,
        query: str,
        session_id: str,
        value: Any,
        ttl: Optional[float] = None
    ) -> None:
        """
        캐시에 결과 저장

        Args:
            query: 쿼리 문자열
            session_id: 세션 ID
            value: 저장할 값
            ttl: TTL (초), None이면 기본값 사용
        """
        key = self._make_key(query, session_id)
        ttl = ttl if ttl is not None else self._default_ttl

        with self._lock:
            # 최대 크기 초과 시 가장 오래된 엔트리 제거
            while len(self._cache) >= self._max_size:
                oldest_key = next(iter(self._cache))
                del self._cache[oldest_key]
                self._stats.evictions += 1

            self._cache[key] = CacheEntry(
                value=value,
                created_at=time.time(),
                ttl=ttl
            )

            logger.debug(f"Cache SET: {query[:50]}... (ttl={ttl}s)")

    def get_schema(self) -> Optional[str]:
        """스키마 캐시 조회"""
        if self._schema_cache is None:
            return None

        schema, cached_at = self._schema_cache
        if time.time() - cached_at > self._schema_ttl:
            self._schema_cache = None
            return None

        return schema

    def set_schema(self, schema: str) -> None:
        """스키마 캐시 저장"""
        self._schema_cache = (schema, time.time())

    def invalidate(self, query: str = None, session_id: str = "") -> int:
        """
        캐시 무효화

        Args:
            query: 특정 쿼리만 무효화 (None이면 전체)
            session_id: 세션 ID

        Returns:
            무효화된 엔트리 수
        """
        with self._lock:
            if query is None:
                count = len(self._cache)
                self._cache.clear()
                self._schema_cache = None
                return count

            key = self._make_key(query, session_id)
            if key in self._cache:
                del self._cache[key]
                return 1
            return 0

    def get_stats(self) -> Dict[str, Any]:
        """캐시 통계 반환"""
        with self._lock:
            return {
                "size": len(self._cache),
                "max_size": self._max_size,
                "hits": self._stats.hits,
                "misses": self._stats.misses,
                "evictions": self._stats.evictions,
                "hit_rate": f"{self._stats.hit_rate:.2%}",
                "schema_cached": self._schema_cache is not None
            }

    def cleanup_expired(self) -> int:
        """만료된 엔트리 정리"""
        with self._lock:
            expired_keys = [
                key for key, entry in self._cache.items()
                if entry.is_expired()
            ]
            for key in expired_keys:
                del self._cache[key]
            self._stats.evictions += len(expired_keys)
            return len(expired_keys)


# =============================================================================
# 싱글톤 인스턴스
# =============================================================================

_cache_instance: Optional[QueryCache] = None
_cache_lock = threading.Lock()


def get_cache(
    max_size: int = 1000,
    default_ttl: float = 300,
    schema_ttl: float = 3600
) -> QueryCache:
    """
    QueryCache 싱글톤 인스턴스 반환

    Args:
        max_size: 최대 캐시 크기
        default_ttl: 기본 TTL (초)
        schema_ttl: 스키마 TTL (초)
    """
    global _cache_instance

    if _cache_instance is None:
        with _cache_lock:
            if _cache_instance is None:
                _cache_instance = QueryCache(
                    max_size=max_size,
                    default_ttl=default_ttl,
                    schema_ttl=schema_ttl
                )

    return _cache_instance


# =============================================================================
# 캐시 데코레이터
# =============================================================================

def cached_query(ttl: float = 300):
    """
    쿼리 결과 캐싱 데코레이터

    Usage:
        @cached_query(ttl=300)
        def execute_query(query: str, session_id: str) -> dict:
            ...
    """
    def decorator(func):
        def wrapper(query: str, session_id: str = "default", *args, **kwargs):
            cache = get_cache()

            # 캐시 조회
            cached_result = cache.get(query, session_id)
            if cached_result is not None:
                return cached_result

            # 실행 및 캐싱
            result = func(query, session_id, *args, **kwargs)
            cache.set(query, session_id, result, ttl)

            return result
        return wrapper
    return decorator
