"""
WMS (Warehouse Management System) Ontology Schema

창고 관리 시스템의 TBox(스키마)를 정의합니다.

Classes:
- Warehouse: 창고
- Zone: 구역 (입고존, 보관존, 출고존)
- Bin: 로케이션 (행-열-레벨)
- InventoryItem: 재고 품목
- InboundOrder: 입고 오더
- OutboundOrder: 출고 오더
"""

from typing import List


WMS_TBOX = """
## WMS 도메인 클래스 (TBox)

### Warehouse (창고)
- 설명: 물류 보관 시설
- 필수 속성: warehouse_id, name
- 선택 속성: address, capacity_m2, capacity_m3, operator

### Zone (구역)
- 설명: 창고 내 기능별 구역
- 필수 속성: zone_id, zone_type
- 선택 속성: warehouse_id, capacity
- 구역 유형: inbound (입고존), storage (보관존), outbound (출고존), picking (피킹존)

### Bin (로케이션)
- 설명: 재고 보관 위치 (행-열-레벨)
- 필수 속성: bin_id, row, column, level
- 선택 속성: zone_id, capacity, status
- 상태값: empty, occupied, reserved

### InventoryItem (재고 품목)
- 설명: 창고에 보관된 재고
- 필수 속성: sku, quantity
- 선택 속성: bin_id, lot_number, expiry_date, last_updated

### InboundOrder (입고 오더)
- 설명: 입고 예정 오더
- 필수 속성: inbound_id
- 선택 속성: expected_date, actual_date, status, shipper_id
- 상태값: scheduled, arrived, receiving, completed, cancelled

### OutboundOrder (출고 오더)
- 설명: 출고 예정 오더
- 필수 속성: outbound_id
- 선택 속성: expected_date, actual_date, status, destination
- 상태값: pending, picking, packed, shipped, cancelled
"""

WMS_RELATIONSHIPS = """
## WMS 도메인 관계 (Relationships)

### BELONGS_TO
- 방향: (Zone)-[:BELONGS_TO]->(Warehouse)
- 설명: 구역이 속한 창고

### LOCATED_IN
- 방향: (Bin)-[:LOCATED_IN]->(Zone)
- 설명: 로케이션이 위치한 구역

### STORED_AT
- 방향: (InventoryItem)-[:STORED_AT]->(Bin)
- 설명: 재고가 보관된 로케이션

### INBOUND_TO
- 방향: (InboundOrder)-[:INBOUND_TO]->(Warehouse)
- 설명: 입고 대상 창고

### OUTBOUND_FROM
- 방향: (OutboundOrder)-[:OUTBOUND_FROM]->(Warehouse)
- 설명: 출고 창고

### CONTAINS_ITEM
- 방향: (InboundOrder)-[:CONTAINS_ITEM]->(InventoryItem)
- 방향: (OutboundOrder)-[:CONTAINS_ITEM]->(InventoryItem)
- 설명: 오더에 포함된 품목

### MANAGED_BY
- 방향: (Warehouse)-[:MANAGED_BY]->(Organization)
- 설명: 창고 운영 조직
"""

WMS_CYPHER_PATTERNS = """
## WMS 주요 Cypher 패턴

### 창고별 재고 현황
MATCH (w:Warehouse)<-[:BELONGS_TO]-(z:Zone)<-[:LOCATED_IN]-(b:Bin)<-[:STORED_AT]-(i:InventoryItem)
WHERE w.name = $warehouse_name
RETURN i.sku, sum(i.quantity) as total_qty, collect(b.bin_id) as locations

### 적재율 계산
MATCH (w:Warehouse)<-[:BELONGS_TO]-(z:Zone)<-[:LOCATED_IN]-(b:Bin)
WITH w, count(b) as total_bins
MATCH (w)<-[:BELONGS_TO]-(z:Zone)<-[:LOCATED_IN]-(b:Bin)<-[:STORED_AT]-(:InventoryItem)
WITH w, total_bins, count(DISTINCT b) as occupied_bins
RETURN w.name, total_bins, occupied_bins,
       round(100.0 * occupied_bins / total_bins, 2) as utilization_pct

### 특정 SKU 위치 조회
MATCH (i:InventoryItem {sku: $sku})-[:STORED_AT]->(b:Bin)-[:LOCATED_IN]->(z:Zone)-[:BELONGS_TO]->(w:Warehouse)
RETURN w.name, z.zone_type, b.bin_id, i.quantity

### 입고 현황
MATCH (io:InboundOrder)-[:INBOUND_TO]->(w:Warehouse)
WHERE io.status IN ['scheduled', 'arrived', 'receiving']
RETURN io.inbound_id, io.status, io.expected_date, w.name

### 출고 현황
MATCH (oo:OutboundOrder)-[:OUTBOUND_FROM]->(w:Warehouse)
WHERE oo.status IN ['pending', 'picking', 'packed']
RETURN oo.outbound_id, oo.status, oo.expected_date, w.name
"""


def get_wms_schema() -> str:
    """WMS 전체 스키마 반환"""
    return f"{WMS_TBOX}\n\n{WMS_RELATIONSHIPS}\n\n{WMS_CYPHER_PATTERNS}"


def get_wms_node_labels() -> List[str]:
    """WMS 도메인 노드 라벨 목록"""
    return [
        "Warehouse", "Zone", "Bin", "InventoryItem",
        "InboundOrder", "OutboundOrder"
    ]


def get_wms_relationship_types() -> List[str]:
    """WMS 도메인 관계 타입 목록"""
    return [
        "BELONGS_TO", "LOCATED_IN", "STORED_AT",
        "INBOUND_TO", "OUTBOUND_FROM", "CONTAINS_ITEM", "MANAGED_BY"
    ]
