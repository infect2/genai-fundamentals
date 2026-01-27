"""
FMS (Fleet Management System) Ontology Schema

차량 관리 시스템의 TBox(스키마)를 정의합니다.

Classes:
- Vehicle: 차량
- Driver: 운전자
- MaintenanceRecord: 정비 기록
- FuelRecord: 주유 기록
- Consumable: 소모품
"""

from typing import List


FMS_TBOX = """
## FMS 도메인 클래스 (TBox)

### Vehicle (차량)
- 설명: 관리 대상 차량
- 필수 속성: vehicle_id, license_plate
- 선택 속성: vehicle_type, brand, model, year, mileage, status
- 상태값: active, inactive, maintenance, retired

### Driver (운전자)
- 설명: 차량 운전자
- 필수 속성: driver_id, name
- 선택 속성: license_number, license_expiry, phone, status, rating

### MaintenanceRecord (정비 기록)
- 설명: 차량 정비 이력
- 필수 속성: maintenance_id, maintenance_type
- 선택 속성: date, mileage, cost, description, next_due_date
- 정비 유형: regular (정기점검), repair (수리), inspection (검사), tire (타이어), oil (오일)

### FuelRecord (주유 기록)
- 설명: 연료 주입 기록
- 필수 속성: fuel_id, date, amount
- 선택 속성: cost, mileage, fuel_type, station

### Consumable (소모품)
- 설명: 차량 소모품 정보
- 필수 속성: consumable_id, name
- 선택 속성: install_date, expected_life_km, current_life_km, status
- 상태값: good, warning, replace_soon, overdue

### RiskScore (위험 점수)
- 설명: 차량/운전자 위험도 평가
- 속성: score, evaluation_date, factors
"""

FMS_RELATIONSHIPS = """
## FMS 도메인 관계 (Relationships)

### ASSIGNED_TO
- 방향: (Driver)-[:ASSIGNED_TO]->(Vehicle)
- 설명: 운전자 배정 차량

### HAS_MAINTENANCE
- 방향: (Vehicle)-[:HAS_MAINTENANCE]->(MaintenanceRecord)
- 설명: 차량 정비 기록

### HAS_FUEL
- 방향: (Vehicle)-[:HAS_FUEL]->(FuelRecord)
- 설명: 차량 주유 기록

### HAS_CONSUMABLE
- 방향: (Vehicle)-[:HAS_CONSUMABLE]->(Consumable)
- 설명: 차량 장착 소모품

### OWNED_BY
- 방향: (Vehicle)-[:OWNED_BY]->(Organization)
- 설명: 차량 소유 조직

### EMPLOYED_BY
- 방향: (Driver)-[:EMPLOYED_BY]->(Organization)
- 설명: 운전자 소속 조직

### HAS_RISK
- 방향: (Vehicle)-[:HAS_RISK]->(RiskScore)
- 방향: (Driver)-[:HAS_RISK]->(RiskScore)
- 설명: 위험도 평가 결과
"""

FMS_CYPHER_PATTERNS = """
## FMS 주요 Cypher 패턴

### 정비 필요 차량 조회
MATCH (v:Vehicle)-[:HAS_MAINTENANCE]->(m:MaintenanceRecord)
WHERE m.next_due_date < date() OR v.status = 'maintenance'
RETURN v.license_plate, v.vehicle_type, m.maintenance_type, m.next_due_date
ORDER BY m.next_due_date

### 차량별 연비 계산
MATCH (v:Vehicle)-[:HAS_FUEL]->(f:FuelRecord)
WITH v, collect(f) as fuels
WHERE size(fuels) >= 2
UNWIND range(1, size(fuels)-1) as idx
WITH v, fuels[idx-1] as prev, fuels[idx] as curr
RETURN v.license_plate,
       avg((curr.mileage - prev.mileage) / curr.amount) as avg_fuel_efficiency

### 운전자별 배정 차량
MATCH (d:Driver)-[:ASSIGNED_TO]->(v:Vehicle)
RETURN d.name, d.rating, collect(v.license_plate) as assigned_vehicles

### 소모품 교체 필요 차량
MATCH (v:Vehicle)-[:HAS_CONSUMABLE]->(c:Consumable)
WHERE c.status IN ['warning', 'replace_soon', 'overdue']
RETURN v.license_plate, c.name, c.status, c.current_life_km, c.expected_life_km

### 차량 상태 통계
MATCH (v:Vehicle)
RETURN v.status, count(v) as count
ORDER BY count DESC
"""


def get_fms_schema() -> str:
    """FMS 전체 스키마 반환"""
    return f"{FMS_TBOX}\n\n{FMS_RELATIONSHIPS}\n\n{FMS_CYPHER_PATTERNS}"


def get_fms_node_labels() -> List[str]:
    """FMS 도메인 노드 라벨 목록"""
    return [
        "Vehicle", "Driver", "MaintenanceRecord",
        "FuelRecord", "Consumable", "RiskScore"
    ]


def get_fms_relationship_types() -> List[str]:
    """FMS 도메인 관계 타입 목록"""
    return [
        "ASSIGNED_TO", "HAS_MAINTENANCE", "HAS_FUEL",
        "HAS_CONSUMABLE", "OWNED_BY", "EMPLOYED_BY", "HAS_RISK"
    ]
