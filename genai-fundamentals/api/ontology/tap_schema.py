"""
TAP! Service Ontology Schema

사용자 호출 서비스의 TBox(스키마)를 정의합니다.

Classes:
- Customer: 고객/사용자
- CallRequest: 호출 요청
- Booking: 예약
- Payment: 결제
- Feedback: 피드백
"""

from typing import List


TAP_TBOX = """
## TAP! 도메인 클래스 (TBox)

### Customer (고객)
- 설명: TAP! 서비스 사용자
- 필수 속성: customer_id
- 선택 속성: name, phone, email, rating, membership_level

### CallRequest (호출 요청)
- 설명: 차량 호출 요청
- 필수 속성: request_id
- 선택 속성: pickup_location, dropoff_location, request_time, eta, status
- 상태값: pending, matched, arriving, in_progress, completed, cancelled

### Booking (예약)
- 설명: 사전 예약 건
- 필수 속성: booking_id
- 선택 속성: scheduled_time, pickup_location, dropoff_location, status
- 상태값: confirmed, pending_payment, cancelled, completed

### Payment (결제)
- 설명: 결제 정보
- 필수 속성: payment_id
- 선택 속성: amount, method, status, paid_at
- 결제 방법: card, cash, points, corporate
- 상태값: pending, completed, refunded, failed

### Feedback (피드백)
- 설명: 서비스 평가/피드백
- 필수 속성: feedback_id
- 선택 속성: rating, comment, created_at, category
- 카테고리: driver, vehicle, app, service

### Location (위치)
- 설명: 픽업/도착 위치
- 필수 속성: location_id
- 선택 속성: address, latitude, longitude, place_name
"""

TAP_RELATIONSHIPS = """
## TAP! 도메인 관계 (Relationships)

### REQUESTED_BY
- 방향: (CallRequest)-[:REQUESTED_BY]->(Customer)
- 설명: 호출 요청 고객

### BOOKED_BY
- 방향: (Booking)-[:BOOKED_BY]->(Customer)
- 설명: 예약 고객

### PICKUP_AT
- 방향: (CallRequest)-[:PICKUP_AT]->(Location)
- 방향: (Booking)-[:PICKUP_AT]->(Location)
- 설명: 픽업 위치

### DROPOFF_AT
- 방향: (CallRequest)-[:DROPOFF_AT]->(Location)
- 방향: (Booking)-[:DROPOFF_AT]->(Location)
- 설명: 도착 위치

### FULFILLED_BY
- 방향: (CallRequest)-[:FULFILLED_BY]->(Vehicle)
- 설명: 배정된 차량

### DRIVEN_BY
- 방향: (CallRequest)-[:DRIVEN_BY]->(Driver)
- 설명: 배정된 운전자

### PAID_WITH
- 방향: (CallRequest)-[:PAID_WITH]->(Payment)
- 방향: (Booking)-[:PAID_WITH]->(Payment)
- 설명: 결제 정보

### HAS_FEEDBACK
- 방향: (CallRequest)-[:HAS_FEEDBACK]->(Feedback)
- 설명: 서비스 피드백
"""

TAP_CYPHER_PATTERNS = """
## TAP! 주요 Cypher 패턴

### 실시간 배정 현황
MATCH (cr:CallRequest)-[:REQUESTED_BY]->(c:Customer)
WHERE cr.status IN ['pending', 'matched', 'arriving']
OPTIONAL MATCH (cr)-[:FULFILLED_BY]->(v:Vehicle)
OPTIONAL MATCH (cr)-[:DRIVEN_BY]->(d:Driver)
RETURN cr.request_id, cr.status, cr.eta, c.name, v.license_plate, d.name

### 고객별 이용 현황
MATCH (c:Customer)<-[:REQUESTED_BY]-(cr:CallRequest)
WHERE c.customer_id = $customer_id
OPTIONAL MATCH (cr)-[:PICKUP_AT]->(pickup:Location)
OPTIONAL MATCH (cr)-[:DROPOFF_AT]->(dropoff:Location)
RETURN cr.request_id, cr.status, cr.request_time, pickup.address, dropoff.address
ORDER BY cr.request_time DESC

### ETA 조회
MATCH (cr:CallRequest {request_id: $request_id})-[:FULFILLED_BY]->(v:Vehicle)
RETURN cr.status, cr.eta, v.license_plate, v.current_location

### 결제 내역
MATCH (c:Customer)<-[:REQUESTED_BY]-(cr:CallRequest)-[:PAID_WITH]->(p:Payment)
WHERE c.customer_id = $customer_id
RETURN cr.request_id, p.amount, p.method, p.status, p.paid_at
ORDER BY p.paid_at DESC

### 피드백 통계
MATCH (fb:Feedback)
RETURN fb.category, avg(fb.rating) as avg_rating, count(fb) as count
ORDER BY avg_rating DESC
"""


def get_tap_schema() -> str:
    """TAP! 전체 스키마 반환"""
    return f"{TAP_TBOX}\n\n{TAP_RELATIONSHIPS}\n\n{TAP_CYPHER_PATTERNS}"


def get_tap_node_labels() -> List[str]:
    """TAP! 도메인 노드 라벨 목록"""
    return [
        "Customer", "CallRequest", "Booking",
        "Payment", "Feedback", "Location"
    ]


def get_tap_relationship_types() -> List[str]:
    """TAP! 도메인 관계 타입 목록"""
    return [
        "REQUESTED_BY", "BOOKED_BY", "PICKUP_AT", "DROPOFF_AT",
        "FULFILLED_BY", "DRIVEN_BY", "PAID_WITH", "HAS_FEEDBACK"
    ]
