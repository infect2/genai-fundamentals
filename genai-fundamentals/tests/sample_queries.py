"""
Sample Queries for Middlemile Logistics Ontology Testing

이 파일은 Middlemile 물류 온톨로지 데이터에 대한 복잡한 테스트 쿼리를 정의합니다.
Agent의 multi-step reasoning 능력과 다양한 RAG 파이프라인을 검증하는 데 사용됩니다.

Usage:
    pytest genai-fundamentals/tests/test_sample_queries.py -v

    # 또는 직접 실행하여 쿼리 확인
    python -m genai-fundamentals.tests.sample_queries
"""

from dataclasses import dataclass
from typing import List, Optional
from enum import Enum


class QueryComplexity(Enum):
    """쿼리 복잡도 레벨"""
    SIMPLE = "simple"           # 단일 노드/관계 조회
    MEDIUM = "medium"           # 2-3 hop 관계, 기본 집계
    COMPLEX = "complex"         # 다중 hop, 복합 조건, 집계
    ADVANCED = "advanced"       # 서브쿼리, 복잡한 패턴 매칭


class ExpectedRoute(Enum):
    """예상 라우팅 타입"""
    CYPHER = "cypher"
    VECTOR = "vector"
    HYBRID = "hybrid"
    LLM_ONLY = "llm_only"


@dataclass
class SampleQuery:
    """테스트 쿼리 정의"""
    id: str                             # 쿼리 식별자
    query_ko: str                       # 한국어 쿼리
    query_en: str                       # 영어 쿼리
    description: str                    # 쿼리 설명
    complexity: QueryComplexity         # 복잡도
    expected_route: ExpectedRoute       # 예상 라우팅
    expected_keywords: List[str]        # 응답에 포함되어야 할 키워드
    min_results: Optional[int] = None   # 최소 예상 결과 수


# =============================================================================
# 복잡한 테스트 쿼리 10개
# =============================================================================

SAMPLE_QUERIES: List[SampleQuery] = [
    # -------------------------------------------------------------------------
    # Query 1: Multi-hop 관계 탐색 (Shipper → Cargo → Shipment → Carrier)
    # -------------------------------------------------------------------------
    SampleQuery(
        id="Q01_MULTI_HOP_SHIPPER_TO_CARRIER",
        query_ko="화주 'Shipper_001'이 보낸 화물을 운송하는 운송사들의 이름과 연락처를 알려줘",
        query_en="Find the carriers transporting cargo from Shipper_001 and show their names and contact info",
        description="""
        Multi-hop relationship traversal:
        (Shipper)-[:OWNS]->(Cargo)<-[:CONTAINS]-(Shipment)-[:FULFILLED_BY]->(Carrier)
        Tests: 4-node path traversal, property extraction
        """,
        complexity=QueryComplexity.COMPLEX,
        expected_route=ExpectedRoute.CYPHER,
        expected_keywords=["Carrier", "contactEmail", "contactPhone"],
        min_results=1
    ),

    # -------------------------------------------------------------------------
    # Query 2: 집계 쿼리 (운송사별 차량 수 및 총 용량)
    # -------------------------------------------------------------------------
    SampleQuery(
        id="Q02_AGGREGATION_CARRIER_VEHICLES",
        query_ko="각 운송사별로 보유한 차량 수와 총 적재 용량(kg)을 계산해서 상위 10개를 보여줘",
        query_en="Calculate the number of vehicles and total capacity (kg) for each carrier, show top 10",
        description="""
        Aggregation query with sorting:
        MATCH (c:Carrier)-[:OPERATES]->(v:Vehicle)
        RETURN c.name, count(v), sum(v.capacityKg) ORDER BY count(v) DESC LIMIT 10
        Tests: GROUP BY, COUNT, SUM, ORDER BY, LIMIT
        """,
        complexity=QueryComplexity.COMPLEX,
        expected_route=ExpectedRoute.CYPHER,
        expected_keywords=["Carrier", "Vehicle", "capacity"],
        min_results=10
    ),

    # -------------------------------------------------------------------------
    # Query 3: 지역 기반 필터링 (특정 물류센터 기준)
    # -------------------------------------------------------------------------
    SampleQuery(
        id="Q03_LOCATION_BASED_SHIPMENTS",
        query_ko="평택 물류센터에서 출발하여 부산항으로 도착하는 배송 건들을 찾아줘",
        query_en="Find shipments departing from Pyeongtaek Logistics Center to Busan Port",
        description="""
        Location-based filtering with origin/destination:
        (lc:LogisticsCenter {name: '평택 물류센터'})<-[:ORIGIN]-(s:Shipment)-[:DESTINATION]->(p:Port {name: '부산항'})
        Tests: Bi-directional relationship, property matching
        """,
        complexity=QueryComplexity.MEDIUM,
        expected_route=ExpectedRoute.CYPHER,
        expected_keywords=["Shipment", "평택", "부산"],
        min_results=0  # 데이터에 따라 다름
    ),

    # -------------------------------------------------------------------------
    # Query 4: 상태 기반 필터링 + 시간 조건
    # -------------------------------------------------------------------------
    SampleQuery(
        id="Q04_STATUS_AND_TIME_FILTER",
        query_ko="현재 '배송중' 상태인 배송 건 중에서 예상 도착일이 가장 빠른 5건을 보여줘",
        query_en="Show top 5 shipments with 'in_transit' status ordered by earliest estimated delivery",
        description="""
        Status filtering with time-based sorting:
        MATCH (s:Shipment {status: 'in_transit'})
        RETURN s ORDER BY s.estimatedDelivery ASC LIMIT 5
        Tests: Property filtering, datetime sorting, LIMIT
        """,
        complexity=QueryComplexity.MEDIUM,
        expected_route=ExpectedRoute.CYPHER,
        expected_keywords=["Shipment", "status", "estimatedDelivery"],
        min_results=1
    ),

    # -------------------------------------------------------------------------
    # Query 5: 복합 조인 (Matching Service 분석)
    # -------------------------------------------------------------------------
    SampleQuery(
        id="Q05_MATCHING_SERVICE_ANALYSIS",
        query_ko="매칭 점수가 0.8 이상인 화주-운송사 매칭 건들을 찾고, 해당 화주와 운송사의 상세 정보를 보여줘",
        query_en="Find shipper-carrier matches with score >= 0.8 and show details of both parties",
        description="""
        Complex join with filtering:
        (ms:MatchingService)-[:MATCHES_SHIPPER]->(sh:Shipper)
        (ms)-[:MATCHES_CARRIER]->(c:Carrier)
        WHERE ms.matchScore >= 0.8
        Tests: Multiple relationships from single node, numeric filtering
        """,
        complexity=QueryComplexity.COMPLEX,
        expected_route=ExpectedRoute.CYPHER,
        expected_keywords=["MatchingService", "matchScore", "Shipper", "Carrier"],
        min_results=1
    ),

    # -------------------------------------------------------------------------
    # Query 6: 시맨틱 검색 (화물 설명 기반)
    # -------------------------------------------------------------------------
    SampleQuery(
        id="Q06_SEMANTIC_CARGO_SEARCH",
        query_ko="냉장 보관이 필요한 식품 관련 화물들을 찾아줘",
        query_en="Find cargo related to food products that require refrigerated storage",
        description="""
        Semantic/vector search on cargo descriptions:
        Uses vector similarity on Cargo.description field
        Tests: Vector search capability, semantic understanding
        """,
        complexity=QueryComplexity.MEDIUM,
        expected_route=ExpectedRoute.VECTOR,
        expected_keywords=["Cargo", "냉장", "식품"],
        min_results=0  # 벡터 인덱스 및 데이터에 따라 다름
    ),

    # -------------------------------------------------------------------------
    # Query 7: 하이브리드 검색 (구조 + 시맨틱)
    # -------------------------------------------------------------------------
    SampleQuery(
        id="Q07_HYBRID_SEARCH",
        query_ko="인천 지역 물류센터에서 출발하는 배송 중 전자제품과 관련된 화물을 찾아줘",
        query_en="Find shipments from Incheon logistics centers containing electronics-related cargo",
        description="""
        Hybrid search combining structure and semantics:
        1. Cypher: Find shipments from Incheon logistics centers
        2. Vector: Filter by cargo description similarity to 'electronics'
        Tests: Combined cypher + vector search
        """,
        complexity=QueryComplexity.ADVANCED,
        expected_route=ExpectedRoute.HYBRID,
        expected_keywords=["인천", "Shipment", "Cargo"],
        min_results=0
    ),

    # -------------------------------------------------------------------------
    # Query 8: 차량 타입별 통계
    # -------------------------------------------------------------------------
    SampleQuery(
        id="Q08_VEHICLE_TYPE_STATISTICS",
        query_ko="차량 타입별로 평균 적재 용량(kg, m3)과 차량 수를 계산하고, 어떤 타입이 가장 많은지 알려줘",
        query_en="Calculate average capacity (kg, m3) and count by vehicle type, identify the most common type",
        description="""
        Aggregation with grouping by enum-like property:
        MATCH (v:Vehicle)
        RETURN v.vehicleType, count(v), avg(v.capacityKg), avg(v.capacityM3)
        ORDER BY count(v) DESC
        Tests: GROUP BY, COUNT, AVG, multiple aggregations
        """,
        complexity=QueryComplexity.COMPLEX,
        expected_route=ExpectedRoute.CYPHER,
        expected_keywords=["vehicleType", "capacity", "count", "average"],
        min_results=1
    ),

    # -------------------------------------------------------------------------
    # Query 9: 경로 분석 (출발지-도착지 패턴)
    # -------------------------------------------------------------------------
    SampleQuery(
        id="Q09_ROUTE_PATTERN_ANALYSIS",
        query_ko="가장 많이 사용되는 출발지-도착지 경로 상위 5개를 찾고, 각 경로별 배송 건수를 보여줘",
        query_en="Find top 5 most frequent origin-destination routes with shipment counts",
        description="""
        Pattern analysis with path counting:
        MATCH (origin)<-[:ORIGIN]-(s:Shipment)-[:DESTINATION]->(dest)
        RETURN origin.name, dest.name, count(s) as shipmentCount
        ORDER BY shipmentCount DESC LIMIT 5
        Tests: Path pattern matching, counting, multi-node aggregation
        """,
        complexity=QueryComplexity.ADVANCED,
        expected_route=ExpectedRoute.CYPHER,
        expected_keywords=["ORIGIN", "DESTINATION", "count"],
        min_results=1
    ),

    # -------------------------------------------------------------------------
    # Query 10: 복합 비즈니스 쿼리 (가격 분석)
    # -------------------------------------------------------------------------
    SampleQuery(
        id="Q10_PRICING_ANALYSIS",
        query_ko="운송사별로 처리한 배송의 평균 가격을 계산하고, 가격 책정 방식(pricingMethod)별로 분류해서 보여줘",
        query_en="Calculate average shipment price per carrier, grouped by pricing method",
        description="""
        Complex business analysis query:
        MATCH (c:Carrier)<-[:FULFILLED_BY]-(s:Shipment)<-[:PRICES]-(ps:PricingService)
        RETURN c.name, ps.pricingMethod, avg(ps.price), count(s)
        Tests: Multi-hop with aggregation, multiple grouping keys
        """,
        complexity=QueryComplexity.ADVANCED,
        expected_route=ExpectedRoute.CYPHER,
        expected_keywords=["Carrier", "PricingService", "price", "pricingMethod"],
        min_results=1
    ),
]


# =============================================================================
# 유틸리티 함수
# =============================================================================

def get_query_by_id(query_id: str) -> Optional[SampleQuery]:
    """ID로 쿼리 조회"""
    for q in SAMPLE_QUERIES:
        if q.id == query_id:
            return q
    return None


def get_queries_by_complexity(complexity: QueryComplexity) -> List[SampleQuery]:
    """복잡도별 쿼리 필터링"""
    return [q for q in SAMPLE_QUERIES if q.complexity == complexity]


def get_queries_by_route(route: ExpectedRoute) -> List[SampleQuery]:
    """라우팅 타입별 쿼리 필터링"""
    return [q for q in SAMPLE_QUERIES if q.expected_route == route]


def print_all_queries(language: str = "ko"):
    """모든 쿼리 출력"""
    print("=" * 80)
    print(f"Middlemile Logistics Sample Queries ({len(SAMPLE_QUERIES)} total)")
    print("=" * 80)

    for i, q in enumerate(SAMPLE_QUERIES, 1):
        query_text = q.query_ko if language == "ko" else q.query_en
        print(f"\n[{i}] {q.id}")
        print(f"    Complexity: {q.complexity.value}")
        print(f"    Route: {q.expected_route.value}")
        print(f"    Query: {query_text}")
        print(f"    Keywords: {', '.join(q.expected_keywords)}")


# =============================================================================
# Main (직접 실행 시)
# =============================================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Sample Queries for Middlemile Logistics")
    parser.add_argument("--lang", choices=["ko", "en"], default="ko", help="Query language")
    parser.add_argument("--complexity", choices=["simple", "medium", "complex", "advanced"],
                        help="Filter by complexity")
    parser.add_argument("--route", choices=["cypher", "vector", "hybrid", "llm_only"],
                        help="Filter by expected route")
    args = parser.parse_args()

    queries = SAMPLE_QUERIES

    if args.complexity:
        queries = get_queries_by_complexity(QueryComplexity(args.complexity))
    if args.route:
        queries = get_queries_by_route(ExpectedRoute(args.route))

    print("=" * 80)
    print(f"Middlemile Logistics Sample Queries ({len(queries)} queries)")
    print("=" * 80)

    for i, q in enumerate(queries, 1):
        query_text = q.query_ko if args.lang == "ko" else q.query_en
        print(f"\n[{i}] {q.id}")
        print(f"    Complexity: {q.complexity.value}")
        print(f"    Route: {q.expected_route.value}")
        print(f"    Query: {query_text}")
        print(f"    Keywords: {', '.join(q.expected_keywords)}")
