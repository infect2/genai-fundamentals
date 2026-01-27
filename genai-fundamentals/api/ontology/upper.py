"""
Upper Ontology Module

물류 시스템의 상위 개념(Upper Ontology)을 정의합니다.
모든 도메인(WMS, TMS, FMS, TAP)에서 공유하는 핵심 개념을 포함합니다.

상위 개념:
- Asset: 자산 (Vehicle, Equipment, Container)
- Participant: 참여자 (Organization, Person)
- Location: 위치 (LogisticsNode, GeographicArea, AddressPoint)
- MovementItem: 이동 객체 (Shipment, InventoryBatch, Order, Task)
- Process: 프로세스 (Movement, Operation, Request)

Usage:
    from genai_fundamentals.api.ontology.upper import (
        get_upper_ontology,
        get_cross_domain_mappings
    )

    upper = get_upper_ontology()
    mappings = get_cross_domain_mappings()
"""

from typing import Dict, List, Tuple


# =============================================================================
# 상위 온톨로지 정의 (Upper Ontology)
# =============================================================================

UPPER_ONTOLOGY = """
# 물류 시스템 상위 온톨로지 (Upper Ontology)

## 1. Asset (자산)
물류 시스템에서 관리되는 물리적/논리적 자산입니다.

### Vehicle (차량)
- 설명: 물류 운송에 사용되는 이동 수단
- 도메인 매핑:
  - FMS: 정비/관리 대상 차량
  - TMS: 운송 수단
  - TAP: 호출 가능 차량
- 속성: vehicle_id, license_plate, vehicle_type, capacity, status

### Equipment (장비)
- 설명: 물류 작업에 사용되는 장비 (지게차, 스캐너 등)
- 도메인 매핑:
  - WMS: 창고 내 작업 장비
  - FMS: 정비 대상
- 속성: equipment_id, equipment_type, location, status

### Container (컨테이너/팔레트)
- 설명: 화물을 담는 용기
- 도메인 매핑:
  - WMS: 보관 단위
  - TMS: 운송 단위
- 속성: container_id, container_type, capacity, current_location


## 2. Participant (참여자)
물류 프로세스에 참여하는 개인 또는 조직입니다.

### Organization (조직)
- 설명: 물류 서비스 관련 기업/기관
- 하위 유형:
  - Shipper (화주): 화물을 보내는 주체
  - Carrier (운송사): 운송 서비스 제공 기업
  - WarehouseOperator (창고운영사): 창고 운영 기업
- 속성: org_id, name, business_number, contact, address

### Person (개인)
- 설명: 물류 작업에 참여하는 개인
- 하위 유형:
  - Driver (운전자): 차량 운전 담당
  - WarehouseWorker (창고직원): 창고 내 작업 담당
  - Dispatcher (배차담당자): 배차 계획 담당
- 속성: person_id, name, phone, role, organization_id


## 3. Location (위치)
물류 활동이 발생하는 장소입니다.

### LogisticsNode (물류 노드)
- 설명: 물류 네트워크의 주요 거점
- 하위 유형:
  - LogisticsCenter (물류센터): 화물 집하/분류 시설
  - Hub (허브): 대규모 중계 거점
  - Port (항구): 해상 운송 항만
  - Depot (차량기지): 차량 보관/관리 시설
- 속성: node_id, name, address, coordinates, capacity

### GeographicArea (지리적 영역)
- 설명: 서비스 권역 또는 행정구역
- 하위 유형:
  - ServiceZone (서비스존): TAP 서비스 가능 영역
  - DeliveryRegion (배송권역): 배송 가능 지역
- 속성: area_id, name, boundary_polygon, parent_area

### AddressPoint (상세 주소)
- 설명: 정확한 위치 정보
- 속성: address_id, full_address, postal_code, latitude, longitude


## 4. MovementItem (이동 객체)
물류 시스템에서 이동하는 대상입니다.

### Shipment (배송)
- 설명: 운송 건 단위
- 도메인: TMS
- 속성: shipment_id, origin, destination, status, eta, weight, volume

### InventoryBatch (재고 배치)
- 설명: 창고 내 재고 단위
- 도메인: WMS
- 속성: batch_id, sku, quantity, location, expiry_date

### Order (주문)
- 설명: 사용자 요청 단위
- 도메인: TAP
- 속성: order_id, customer_id, pickup_location, dropoff_location, status

### Task (작업)
- 설명: 수행해야 할 단위 작업
- 도메인: FMS
- 속성: task_id, task_type, vehicle_id, due_date, status


## 5. Process (프로세스)
물류 활동의 단위 프로세스입니다.

### Movement (이동)
- 설명: 물리적 이동 활동
- 하위 유형:
  - Pickup (픽업): 출발지에서 화물 수령
  - Delivery (배송): 목적지로 화물 전달
  - Transfer (이송): 거점 간 이동
- 속성: movement_id, item_id, from_location, to_location, start_time, end_time

### Operation (작업)
- 설명: 창고 내 작업 활동
- 하위 유형:
  - Inbound (입고): 창고로 화물 입고
  - Putaway (적치): 지정 위치에 보관
  - Picking (피킹): 출고용 화물 집품
  - Outbound (출고): 창고에서 화물 출고
- 속성: operation_id, operation_type, item_id, location_id, timestamp

### Request (요청)
- 설명: 서비스 요청 활동
- 하위 유형:
  - QuoteRequest (견적요청): 운송 견적 요청
  - BookingRequest (예약요청): 운송 예약 요청
  - CallRequest (호출요청): TAP 차량 호출
- 속성: request_id, requester_id, request_type, details, status
"""


# =============================================================================
# 크로스 도메인 매핑
# =============================================================================

CROSS_DOMAIN_MAPPINGS: Dict[Tuple[str, str], List[Tuple[str, str]]] = {
    # (source_domain, source_class) -> [(target_domain, target_class), ...]

    # Vehicle 매핑
    ("fms", "Vehicle"): [
        ("tms", "TransportAsset"),
        ("tap", "CallableVehicle")
    ],
    ("tms", "TransportAsset"): [
        ("fms", "Vehicle"),
        ("tap", "CallableVehicle")
    ],
    ("tap", "CallableVehicle"): [
        ("fms", "Vehicle"),
        ("tms", "TransportAsset")
    ],

    # Inventory/Cargo 매핑
    ("wms", "Inventory"): [
        ("tms", "Cargo")
    ],
    ("tms", "Cargo"): [
        ("wms", "Inventory")
    ],

    # Order/Shipment 매핑
    ("tap", "Order"): [
        ("tms", "Shipment"),
        ("wms", "OutboundRequest")
    ],
    ("tms", "Shipment"): [
        ("tap", "Order"),
        ("wms", "OutboundRequest")
    ],

    # Carrier/Organization 매핑
    ("tms", "Carrier"): [
        ("fms", "FleetOwner"),
        ("tap", "ServiceProvider")
    ],

    # Location 매핑
    ("wms", "Warehouse"): [
        ("tms", "Origin"),
        ("tms", "Destination"),
        ("tap", "PickupPoint")
    ],
}


# =============================================================================
# 유틸리티 함수
# =============================================================================

def get_upper_ontology() -> str:
    """
    상위 온톨로지 문자열 반환

    Returns:
        상위 온톨로지 설명 문자열
    """
    return UPPER_ONTOLOGY


def get_cross_domain_mappings() -> Dict[Tuple[str, str], List[Tuple[str, str]]]:
    """
    크로스 도메인 매핑 딕셔너리 반환

    Returns:
        (source_domain, source_class) -> [(target_domain, target_class), ...] 매핑
    """
    return CROSS_DOMAIN_MAPPINGS


def get_equivalent_classes(domain: str, class_name: str) -> List[Tuple[str, str]]:
    """
    특정 클래스의 다른 도메인 동등 클래스 목록 반환

    Args:
        domain: 소스 도메인 (e.g., "fms")
        class_name: 클래스 이름 (e.g., "Vehicle")

    Returns:
        [(target_domain, target_class), ...] 리스트
    """
    key = (domain.lower(), class_name)
    return CROSS_DOMAIN_MAPPINGS.get(key, [])


def format_for_llm(include_mappings: bool = True) -> str:
    """
    LLM 프롬프트용 포맷팅된 온톨로지 문자열 반환

    Args:
        include_mappings: 크로스 도메인 매핑 포함 여부

    Returns:
        포맷팅된 문자열
    """
    result = UPPER_ONTOLOGY

    if include_mappings:
        result += "\n\n# 크로스 도메인 매핑\n"
        result += "다음은 도메인 간 동등 개념 매핑입니다:\n\n"

        for (src_domain, src_class), targets in CROSS_DOMAIN_MAPPINGS.items():
            target_str = ", ".join(f"{d}.{c}" for d, c in targets)
            result += f"- {src_domain}.{src_class} ↔ {target_str}\n"

    return result
