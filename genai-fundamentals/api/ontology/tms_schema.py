"""
TMS (Transportation Management System) Ontology Schema

운송 관리 시스템의 TBox(스키마)를 정의합니다.
Middlemile 물류 온톨로지를 기반으로 확장합니다.

Classes:
- Shipment: 배송 건
- Carrier: 운송사
- Shipper: 화주
- Vehicle: 차량
- Location: 위치 (LogisticsCenter, Port)
- Cargo: 화물

Relationships:
- REQUESTED_BY: Shipment → Shipper
- FULFILLED_BY: Shipment → Carrier
- ASSIGNED_TO: Shipment → Vehicle
- ORIGIN: Shipment → Location
- DESTINATION: Shipment → Location
- CONTAINS: Shipment → Cargo
"""

from typing import Dict, List


# =============================================================================
# TMS TBox (Schema Definition)
# =============================================================================

TMS_TBOX = """
## TMS 도메인 클래스 (TBox)

### Shipment (배송)
- 설명: 화물 운송 건 단위
- 필수 속성: shipment_id
- 선택 속성: status, requested_date, pickup_date, delivery_date, weight, volume
- 상태값: requested, matched, pickup_pending, in_transit, delivered, cancelled

### Carrier (운송사)
- 설명: 운송 서비스를 제공하는 기업
- 필수 속성: name
- 선택 속성: business_number, contact, service_region, rating

### Shipper (화주)
- 설명: 화물을 보내는 기업/개인
- 필수 속성: name
- 선택 속성: business_number, contact, address

### Vehicle (차량)
- 설명: 운송에 사용되는 차량
- 필수 속성: license_plate, vehicle_type
- 선택 속성: capacity_kg, capacity_m3, status
- 차량유형: 1톤트럭, 2.5톤트럭, 5톤트럭, 11톤트럭, 25톤트럭, 윙바디, 냉동냉장차, 컨테이너, 탱크로리, 평판차

### Location (위치)
- 설명: 물류 관련 위치 (상위 클래스)
- 하위 클래스:
  - LogisticsCenter (물류센터): 화물 집하/분류 시설
  - Port (항구): 해상 운송 항만
- 필수 속성: name
- 선택 속성: address, latitude, longitude

### Cargo (화물)
- 설명: 운송 대상 물품
- 필수 속성: cargo_type
- 선택 속성: weight, volume, description

### MatchingService (매칭서비스)
- 설명: 화주-운송사 매칭 서비스
- 속성: match_score, matched_at

### PricingService (가격책정서비스)
- 설명: 동적 가격 책정 서비스
- 속성: base_price, final_price, discount_rate

### ConsolidationService (합적서비스)
- 설명: 여러 화물을 합쳐서 운송하는 서비스
- 속성: consolidation_date, cargo_count
"""

TMS_RELATIONSHIPS = """
## TMS 도메인 관계 (Relationships)

### REQUESTED_BY
- 방향: (Shipment)-[:REQUESTED_BY]->(Shipper)
- 설명: 배송을 요청한 화주

### FULFILLED_BY
- 방향: (Shipment)-[:FULFILLED_BY]->(Carrier)
- 설명: 배송을 수행하는 운송사

### ASSIGNED_TO
- 방향: (Shipment)-[:ASSIGNED_TO]->(Vehicle)
- 설명: 배송에 배정된 차량

### ORIGIN
- 방향: (Shipment)-[:ORIGIN]->(Location)
- 설명: 배송 출발지

### DESTINATION
- 방향: (Shipment)-[:DESTINATION]->(Location)
- 설명: 배송 목적지

### CONTAINS
- 방향: (Shipment)-[:CONTAINS]->(Cargo)
- 설명: 배송에 포함된 화물

### OPERATES
- 방향: (Carrier)-[:OPERATES]->(Vehicle)
- 설명: 운송사가 운영하는 차량

### OWNS
- 방향: (Shipper)-[:OWNS]->(Cargo)
- 설명: 화주가 소유한 화물

### MATCHES_SHIPPER
- 방향: (MatchingService)-[:MATCHES_SHIPPER]->(Shipper)
- 설명: 매칭된 화주

### MATCHES_CARRIER
- 방향: (MatchingService)-[:MATCHES_CARRIER]->(Carrier)
- 설명: 매칭된 운송사

### PRICES
- 방향: (PricingService)-[:PRICES]->(Shipment)
- 설명: 가격 책정 대상 배송

### CONSOLIDATES
- 방향: (ConsolidationService)-[:CONSOLIDATES]->(Cargo)
- 설명: 합적 대상 화물

### LOCATED_AT
- 방향: (Carrier)-[:LOCATED_AT]->(Location)
- 설명: 운송사 위치

### SERVES_REGION
- 방향: (Carrier)-[:SERVES_REGION]->(Location)
- 설명: 운송사 서비스 지역
"""

TMS_CYPHER_PATTERNS = """
## TMS 주요 Cypher 패턴

### 배송 현황 조회
MATCH (s:Shipment)-[:REQUESTED_BY]->(shipper:Shipper)
OPTIONAL MATCH (s)-[:FULFILLED_BY]->(carrier:Carrier)
OPTIONAL MATCH (s)-[:ASSIGNED_TO]->(v:Vehicle)
OPTIONAL MATCH (s)-[:ORIGIN]->(origin:Location)
OPTIONAL MATCH (s)-[:DESTINATION]->(dest:Location)
WHERE s.status = 'in_transit'
RETURN s, shipper, carrier, v, origin, dest

### 운송사별 배송 통계
MATCH (carrier:Carrier)<-[:FULFILLED_BY]-(s:Shipment)
RETURN carrier.name, count(s) as shipment_count
ORDER BY shipment_count DESC

### 특정 화주의 배송 목록
MATCH (shipper:Shipper {name: $shipper_name})<-[:REQUESTED_BY]-(s:Shipment)
OPTIONAL MATCH (s)-[:ORIGIN]->(origin)
OPTIONAL MATCH (s)-[:DESTINATION]->(dest)
RETURN s.shipment_id, s.status, origin.name, dest.name

### 경로별 배송 조회
MATCH (s:Shipment)-[:ORIGIN]->(origin:Location)
MATCH (s)-[:DESTINATION]->(dest:Location)
WHERE origin.name = $origin_name AND dest.name = $dest_name
RETURN s, origin, dest

### 차량별 배송 현황
MATCH (v:Vehicle)<-[:ASSIGNED_TO]-(s:Shipment)
WHERE v.license_plate = $plate
RETURN v, collect(s) as shipments
"""


# =============================================================================
# 유틸리티 함수
# =============================================================================

def get_tms_schema() -> str:
    """
    TMS 전체 스키마 문자열 반환

    Returns:
        TBox + 관계 + Cypher 패턴
    """
    return f"{TMS_TBOX}\n\n{TMS_RELATIONSHIPS}\n\n{TMS_CYPHER_PATTERNS}"


def get_tms_tbox() -> str:
    """TMS TBox만 반환"""
    return TMS_TBOX


def get_tms_relationships() -> str:
    """TMS 관계 정의만 반환"""
    return TMS_RELATIONSHIPS


def get_tms_cypher_patterns() -> str:
    """TMS Cypher 패턴만 반환"""
    return TMS_CYPHER_PATTERNS


def get_tms_node_labels() -> List[str]:
    """TMS 도메인 노드 라벨 목록"""
    return [
        "Shipment",
        "Carrier",
        "Shipper",
        "Vehicle",
        "Location",
        "LogisticsCenter",
        "Port",
        "Cargo",
        "MatchingService",
        "PricingService",
        "ConsolidationService",
    ]


def get_tms_relationship_types() -> List[str]:
    """TMS 도메인 관계 타입 목록"""
    return [
        "REQUESTED_BY",
        "FULFILLED_BY",
        "ASSIGNED_TO",
        "ORIGIN",
        "DESTINATION",
        "CONTAINS",
        "OPERATES",
        "OWNS",
        "MATCHES_SHIPPER",
        "MATCHES_CARRIER",
        "PRICES",
        "CONSOLIDATES",
        "LOCATED_AT",
        "SERVES_REGION",
    ]


def get_shipment_statuses() -> List[str]:
    """배송 상태 값 목록"""
    return [
        "requested",      # 요청됨
        "matched",        # 매칭됨
        "pickup_pending", # 픽업 대기
        "in_transit",     # 운송 중
        "delivered",      # 배송 완료
        "cancelled",      # 취소됨
    ]


def get_vehicle_types() -> List[str]:
    """차량 유형 목록"""
    return [
        "1톤트럭",
        "2.5톤트럭",
        "5톤트럭",
        "11톤트럭",
        "25톤트럭",
        "윙바디",
        "냉동냉장차",
        "컨테이너",
        "탱크로리",
        "평판차",
    ]
