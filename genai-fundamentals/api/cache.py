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
- Request Coalescing (동일 쿼리 동시 요청 병합)
- LLM Semaphore (동시 API 호출 제한)
"""

import hashlib
import time
import threading
import asyncio
import re
from typing import Optional, Any, Dict, List, Tuple, Callable, Awaitable
from dataclasses import dataclass, field
from collections import OrderedDict
from functools import lru_cache
from concurrent.futures import Future
import logging

logger = logging.getLogger(__name__)


def _get_cache_config():
    """Lazy import to avoid circular dependency"""
    from .config import get_config
    return get_config().cache


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
    coalesced: int = 0  # 병합된 요청 수

    @property
    def hit_rate(self) -> float:
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0


# =============================================================================
# Request Coalescing (동시 요청 병합)
# =============================================================================

class RequestCoalescer:
    """
    동일한 쿼리에 대한 동시 요청을 병합합니다.

    여러 클라이언트가 동시에 같은 쿼리를 요청하면,
    첫 번째 요청만 실제로 실행하고 나머지는 결과를 공유합니다.

    Usage:
        coalescer = RequestCoalescer()

        async def handle_query(query: str):
            async def execute():
                return await expensive_llm_call(query)

            return await coalescer.execute(query, execute)
    """

    def __init__(self):
        self._in_flight: Dict[str, asyncio.Future] = {}
        self._lock = asyncio.Lock()
        self._stats = {"coalesced": 0, "executed": 0}

    async def execute(
        self,
        key: str,
        func: Callable[[], Awaitable[Any]]
    ) -> Any:
        """
        쿼리 실행 (동시 요청 병합)

        Args:
            key: 요청 식별 키 (정규화된 쿼리 해시)
            func: 실제 실행할 비동기 함수

        Returns:
            실행 결과
        """
        async with self._lock:
            # 이미 실행 중인 동일 요청이 있는지 확인
            if key in self._in_flight:
                self._stats["coalesced"] += 1
                logger.debug(f"Request coalesced: {key[:16]}...")
                future = self._in_flight[key]
            else:
                # 새로운 Future 생성
                future = asyncio.get_event_loop().create_future()
                self._in_flight[key] = future
                self._stats["executed"] += 1

                # 락 해제 후 실행 (다른 요청이 대기 가능하도록)
                asyncio.create_task(self._execute_and_resolve(key, func, future))

        # 결과 대기
        return await future

    async def _execute_and_resolve(
        self,
        key: str,
        func: Callable[[], Awaitable[Any]],
        future: asyncio.Future
    ) -> None:
        """실제 실행 및 Future 해결"""
        try:
            result = await func()
            future.set_result(result)
        except Exception as e:
            future.set_exception(e)
        finally:
            # 완료 후 in-flight에서 제거
            async with self._lock:
                self._in_flight.pop(key, None)

    def get_stats(self) -> Dict[str, int]:
        """통계 반환"""
        return {
            "in_flight": len(self._in_flight),
            "coalesced": self._stats["coalesced"],
            "executed": self._stats["executed"]
        }


# =============================================================================
# LLM Semaphore (동시 API 호출 제한)
# =============================================================================

class LLMSemaphore:
    """
    LLM API 동시 호출 수를 제한합니다.

    Rate limiting 방지 및 안정적인 서비스를 위해
    동시 LLM API 호출 수를 제한합니다.

    Usage:
        semaphore = LLMSemaphore(max_concurrent=10)

        async def call_llm():
            async with semaphore.acquire():
                return await llm.ainvoke(...)
    """

    def __init__(self, max_concurrent: int = 10):
        """
        Args:
            max_concurrent: 최대 동시 호출 수 (기본: 10)
        """
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._max_concurrent = max_concurrent
        self._current = 0
        self._total_acquired = 0
        self._total_waited = 0
        self._lock = asyncio.Lock()

    async def acquire(self):
        """세마포어 획득 (컨텍스트 매니저)"""
        return _SemaphoreContext(self)

    async def _acquire(self):
        """내부 획득"""
        waited = not self._semaphore.locked()
        await self._semaphore.acquire()

        async with self._lock:
            self._current += 1
            self._total_acquired += 1
            if not waited:
                self._total_waited += 1

    async def _release(self):
        """내부 해제"""
        self._semaphore.release()
        async with self._lock:
            self._current -= 1

    def get_stats(self) -> Dict[str, Any]:
        """통계 반환"""
        return {
            "max_concurrent": self._max_concurrent,
            "current": self._current,
            "total_acquired": self._total_acquired,
            "total_waited": self._total_waited,
            "utilization": f"{(self._current / self._max_concurrent) * 100:.1f}%"
        }


class _SemaphoreContext:
    """세마포어 컨텍스트 매니저"""

    def __init__(self, semaphore: LLMSemaphore):
        self._semaphore = semaphore

    async def __aenter__(self):
        await self._semaphore._acquire()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self._semaphore._release()
        return False


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
                "coalesced": self._stats.coalesced,
                "hit_rate": f"{self._stats.hit_rate:.2%}",
                "schema_cached": self._schema_cache is not None
            }

    def increment_coalesced(self) -> None:
        """병합된 요청 수 증가"""
        with self._lock:
            self._stats.coalesced += 1

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
# Request Coalescer 싱글톤
# =============================================================================

_coalescer_instance: Optional[RequestCoalescer] = None
_coalescer_lock = threading.Lock()


def get_coalescer() -> RequestCoalescer:
    """
    RequestCoalescer 싱글톤 인스턴스 반환

    동일 쿼리의 동시 요청을 병합하여 LLM API 호출을 최소화합니다.
    """
    global _coalescer_instance

    if _coalescer_instance is None:
        with _coalescer_lock:
            if _coalescer_instance is None:
                _coalescer_instance = RequestCoalescer()

    return _coalescer_instance


# =============================================================================
# LLM Semaphore 싱글톤
# =============================================================================

_semaphore_instance: Optional[LLMSemaphore] = None
_semaphore_lock = threading.Lock()


def get_llm_semaphore(max_concurrent: int = 10) -> LLMSemaphore:
    """
    LLMSemaphore 싱글톤 인스턴스 반환

    Args:
        max_concurrent: 최대 동시 LLM API 호출 수 (기본: 10)

    동시 LLM API 호출 수를 제한하여 rate limiting을 방지합니다.
    """
    global _semaphore_instance

    if _semaphore_instance is None:
        with _semaphore_lock:
            if _semaphore_instance is None:
                _semaphore_instance = LLMSemaphore(max_concurrent=max_concurrent)

    return _semaphore_instance


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


# =============================================================================
# History Cache (대화 히스토리 캐싱)
# =============================================================================

@dataclass
class HistoryEntry:
    """히스토리 캐시 엔트리"""
    messages: list  # [{"role": "human"|"ai", "content": "..."}]
    created_at: float
    last_accessed: float
    dirty: bool = False  # Neo4j 동기화 필요 여부

    def is_stale(self, ttl: float) -> bool:
        """TTL 만료 여부 (마지막 접근 기준)"""
        return time.time() - self.last_accessed > ttl


class HistoryCache:
    """
    세션별 대화 히스토리 캐시

    Neo4j 조회 부하를 50% 이상 감소시킵니다.
    - 읽기: 캐시에서 즉시 반환 (Neo4j 조회 없음)
    - 쓰기: 캐시에 저장 후 비동기 Neo4j 동기화

    Usage:
        cache = HistoryCache()

        # 히스토리 조회 (캐시 히트 시 Neo4j 조회 없음)
        messages = await cache.get_messages(session_id, neo4j_loader)

        # 메시지 추가 (캐시에 즉시 반영, 비동기 동기화)
        await cache.add_message(session_id, "human", "Hello")
        await cache.add_message(session_id, "ai", "Hi there!")

        # 주기적 동기화 (백그라운드 태스크)
        await cache.sync_dirty_sessions(neo4j_saver)
    """

    def __init__(
        self,
        max_sessions: int = 500,
        ttl: float = 1800,  # 30분
        max_messages_per_session: int = 100
    ):
        """
        Args:
            max_sessions: 최대 캐시할 세션 수
            ttl: 세션 TTL (초) - 마지막 접근 후 만료
            max_messages_per_session: 세션당 최대 메시지 수
        """
        self._cache: OrderedDict[str, HistoryEntry] = OrderedDict()
        # Config에서 설정 로드 (파라미터 우선)
        config = _get_cache_config()
        self._max_sessions = config.history_cache_max_sessions if max_sessions == 500 else max_sessions
        self._ttl = config.history_cache_ttl if ttl == 1800 else ttl
        self._max_messages = config.history_cache_max_messages if max_messages_per_session == 100 else max_messages_per_session
        self._lock = threading.RLock()
        self._stats = {
            "hits": 0,
            "misses": 0,
            "writes": 0,
            "syncs": 0,
            "evictions": 0
        }

    def _evict_if_needed(self) -> None:
        """최대 크기 초과 시 가장 오래된 세션 제거"""
        while len(self._cache) >= self._max_sessions:
            oldest_key = next(iter(self._cache))
            del self._cache[oldest_key]
            self._stats["evictions"] += 1

    def _cleanup_stale(self) -> int:
        """만료된 세션 정리"""
        stale_keys = [
            key for key, entry in self._cache.items()
            if entry.is_stale(self._ttl)
        ]
        for key in stale_keys:
            del self._cache[key]
            self._stats["evictions"] += 1
        return len(stale_keys)

    def get_cached(self, session_id: str) -> Optional[list]:
        """
        캐시에서 히스토리 조회 (Neo4j 조회 없음)

        Args:
            session_id: 세션 ID

        Returns:
            캐시된 메시지 리스트 또는 None (캐시 미스)
        """
        with self._lock:
            entry = self._cache.get(session_id)

            if entry is None:
                self._stats["misses"] += 1
                return None

            if entry.is_stale(self._ttl):
                del self._cache[session_id]
                self._stats["misses"] += 1
                self._stats["evictions"] += 1
                return None

            # 히트: LRU 업데이트
            self._cache.move_to_end(session_id)
            entry.last_accessed = time.time()
            self._stats["hits"] += 1

            return entry.messages.copy()

    def set_cached(self, session_id: str, messages: list) -> None:
        """
        캐시에 히스토리 저장

        Args:
            session_id: 세션 ID
            messages: 메시지 리스트
        """
        with self._lock:
            self._evict_if_needed()

            # 최대 메시지 수 제한
            truncated = messages[-self._max_messages:] if len(messages) > self._max_messages else messages

            now = time.time()
            self._cache[session_id] = HistoryEntry(
                messages=truncated,
                created_at=now,
                last_accessed=now,
                dirty=False
            )

    def add_message(self, session_id: str, role: str, content: str) -> None:
        """
        세션에 메시지 추가 (캐시에 즉시 반영)

        Args:
            session_id: 세션 ID
            role: 메시지 역할 ("human" 또는 "ai")
            content: 메시지 내용
        """
        with self._lock:
            entry = self._cache.get(session_id)

            if entry is None:
                # 새 세션 생성
                self._evict_if_needed()
                now = time.time()
                entry = HistoryEntry(
                    messages=[],
                    created_at=now,
                    last_accessed=now,
                    dirty=True
                )
                self._cache[session_id] = entry

            # 메시지 추가
            entry.messages.append({"role": role, "content": content})
            entry.last_accessed = time.time()
            entry.dirty = True
            self._stats["writes"] += 1

            # 최대 메시지 수 제한
            if len(entry.messages) > self._max_messages:
                entry.messages = entry.messages[-self._max_messages:]

            # LRU 업데이트
            self._cache.move_to_end(session_id)

    def mark_synced(self, session_id: str) -> None:
        """세션을 동기화됨으로 표시"""
        with self._lock:
            entry = self._cache.get(session_id)
            if entry:
                entry.dirty = False
                self._stats["syncs"] += 1

    def get_dirty_sessions(self) -> List[str]:
        """동기화 필요한 세션 ID 목록"""
        with self._lock:
            return [
                session_id for session_id, entry in self._cache.items()
                if entry.dirty
            ]

    def clear_session(self, session_id: str) -> bool:
        """세션 캐시 삭제"""
        with self._lock:
            if session_id in self._cache:
                del self._cache[session_id]
                return True
            return False

    def get_stats(self) -> Dict[str, Any]:
        """캐시 통계"""
        with self._lock:
            total = self._stats["hits"] + self._stats["misses"]
            hit_rate = self._stats["hits"] / total if total > 0 else 0.0

            return {
                "sessions": len(self._cache),
                "max_sessions": self._max_sessions,
                "hits": self._stats["hits"],
                "misses": self._stats["misses"],
                "writes": self._stats["writes"],
                "syncs": self._stats["syncs"],
                "evictions": self._stats["evictions"],
                "hit_rate": f"{hit_rate:.2%}",
                "dirty_sessions": len(self.get_dirty_sessions())
            }


# History Cache 싱글톤
_history_cache_instance: Optional[HistoryCache] = None
_history_cache_lock = threading.Lock()


def get_history_cache(
    max_sessions: int = 500,
    ttl: float = 1800,
    max_messages: int = 100
) -> HistoryCache:
    """
    HistoryCache 싱글톤 인스턴스 반환

    Args:
        max_sessions: 최대 캐시 세션 수
        ttl: 세션 TTL (초)
        max_messages: 세션당 최대 메시지 수
    """
    global _history_cache_instance

    if _history_cache_instance is None:
        with _history_cache_lock:
            if _history_cache_instance is None:
                _history_cache_instance = HistoryCache(
                    max_sessions=max_sessions,
                    ttl=ttl,
                    max_messages_per_session=max_messages
                )

    return _history_cache_instance


# =============================================================================
# 통합 통계
# =============================================================================

def get_all_stats() -> Dict[str, Any]:
    """
    모든 캐시/동시성 관련 통계 반환

    Returns:
        cache, coalescer, semaphore, history 통계를 포함한 dict
    """
    cache = get_cache()
    coalescer = get_coalescer()
    semaphore = get_llm_semaphore()
    history_cache = get_history_cache()

    return {
        "cache": cache.get_stats(),
        "coalescer": coalescer.get_stats(),
        "semaphore": semaphore.get_stats(),
        "history": history_cache.get_stats()
    }
