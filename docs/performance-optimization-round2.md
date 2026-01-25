# Performance Optimization Round 2

## 목표
콜드 쿼리 응답 시간 단축 및 캐시 히트율 향상

## 현재 성능
- 캐시 히트: ~0.01s (241 QPS)
- 콜드 쿼리: ~4.7s (LLM API 레이턴시)

## 최적화 계획

### Phase 1: Schema 캐싱 (P0)
**예상 효과:** 50-100ms 절감/쿼리

**파일:** `api/graphrag_service.py` (라인 249-258)

```python
def get_schema(self) -> str:
    from .cache import get_cache
    cache = get_cache()

    cached_schema = cache.get_schema()
    if cached_schema is not None:
        return cached_schema

    schema = self._graph.schema
    cache.set_schema(schema)
    return schema
```

---

### Phase 2: Router 결정 캐싱 (P0)
**예상 효과:** 500-1000ms 절감/반복 쿼리

**파일 1:** `api/cache.py` - 새 메서드 추가

```python
_ROUTER_CACHE_TTL = 300  # 5분

def _make_router_key(self, query: str) -> str:
    normalized = self._normalize_query(query)
    return f"router:{hashlib.md5(normalized.encode()).hexdigest()}"

def get_router_decision(self, query: str) -> Optional[dict]:
    """Router 결정 캐시 조회"""
    key = self._make_router_key(query)
    with self._lock:
        entry = self._cache.get(key)
        if entry is None or entry.is_expired():
            if entry: del self._cache[key]
            return None
        self._cache.move_to_end(key)
        entry.hits += 1
        self._stats.hits += 1
        return entry.value

def set_router_decision(self, query: str, decision: dict) -> None:
    """Router 결정 캐시 저장"""
    key = self._make_router_key(query)
    with self._lock:
        while len(self._cache) >= self._max_size:
            del self._cache[next(iter(self._cache))]
            self._stats.evictions += 1
        self._cache[key] = CacheEntry(value=decision, created_at=time.time(), ttl=self._ROUTER_CACHE_TTL)
```

**파일 2:** `api/graphrag_service.py` - query() 메서드 수정 (라인 309-318)

```python
# Router 캐시 확인
from .cache import get_cache
cache = get_cache()

cached_decision = cache.get_router_decision(query_text)
if cached_decision:
    route_decision = RouteDecision(
        route=RouteType(cached_decision["route"]),
        confidence=cached_decision["confidence"],
        reasoning=cached_decision["reasoning"] + " (cached)"
    )
elif force_route:
    # 기존 로직...
elif self._enable_routing:
    route_decision = self._router.route_sync(query_text)
    cache.set_router_decision(query_text, {
        "route": route_decision.route.value,
        "confidence": route_decision.confidence,
        "reasoning": route_decision.reasoning
    })
```

---

### Phase 3: Embedding 캐싱 (P1)
**예상 효과:** 200-500ms 절감/반복 쿼리

**파일 1:** `api/cache.py` - 임베딩 캐시 메서드 추가

```python
_EMBEDDING_CACHE_TTL = 3600  # 1시간

def _make_embedding_key(self, query: str) -> str:
    normalized = self._normalize_query(query)
    return f"embed:{hashlib.md5(normalized.encode()).hexdigest()}"

def get_embedding(self, query: str) -> Optional[List[float]]:
    """임베딩 캐시 조회"""
    # get_router_decision과 동일한 패턴

def set_embedding(self, query: str, embedding: List[float]) -> None:
    """임베딩 캐시 저장"""
    # set_router_decision과 동일한 패턴, TTL=_EMBEDDING_CACHE_TTL
```

**파일 2:** `api/pipelines/vector.py` - execute() 수정

```python
from ..cache import get_cache
cache = get_cache()

cached_embedding = cache.get_embedding(query_text)
if cached_embedding:
    docs = vector_store.similarity_search_by_vector(cached_embedding, k=top_k)
else:
    docs = vector_store.similarity_search(query_text, k=top_k)
    try:
        embedding = vector_store._embedding.embed_query(query_text)
        cache.set_embedding(query_text, embedding)
    except: pass
```

---

### Phase 4: Hybrid 병렬 실행 (P1)
**예상 효과:** 500ms 절감/hybrid 쿼리

**파일:** `api/pipelines/hybrid.py`

```python
from concurrent.futures import ThreadPoolExecutor

def execute(...):
    with ThreadPoolExecutor(max_workers=2) as executor:
        vector_future = executor.submit(vector_store.similarity_search, query_text, top_k)
        cypher_future = executor.submit(chain.invoke, {"query": query_text})

        docs = vector_future.result()
        cypher_result = cypher_future.result()
    # 이후 기존 로직...
```

---

## 수정 파일 요약

| 파일 | 변경 내용 |
|------|----------|
| `api/cache.py` | Router 캐시, Embedding 캐시 메서드 추가 |
| `api/graphrag_service.py` | Schema 캐시, Router 캐시 통합 |
| `api/pipelines/vector.py` | Embedding 캐시 사용 |
| `api/pipelines/hybrid.py` | 병렬 실행 (ThreadPoolExecutor) |

---

## 검증 방법

```bash
# 1. 서버 시작
python -m genai-fundamentals.api.server

# 2. 캐시 초기화
curl -X POST http://localhost:8000/cache/clear

# 3. 콜드 쿼리 실행
time curl -X POST http://localhost:8000/agent/query \
  -H "Content-Type: application/json" \
  -d '{"query": "배송 현황 알려줘"}'

# 4. 동일 쿼리 재실행 (캐시 히트 확인)
time curl -X POST http://localhost:8000/agent/query \
  -H "Content-Type: application/json" \
  -d '{"query": "배송 현황 알려줘"}'

# 5. 캐시 통계 확인
curl http://localhost:8000/cache/stats
```

---

## 예상 결과

| 시나리오 | 현재 | 최적화 후 |
|---------|------|----------|
| 스키마 조회 | ~100ms | ~1ms (캐시) |
| 라우터 결정 | ~500ms | ~1ms (캐시) |
| 임베딩 생성 | ~300ms | ~1ms (캐시) |
| Hybrid 쿼리 | 순차 | 병렬 (-500ms) |
| **총 콜드 쿼리** | ~4.7s | ~3.5s (-25%) |
