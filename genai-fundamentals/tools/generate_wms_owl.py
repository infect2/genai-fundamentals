# =============================================================================
# WMS (Warehouse Management System) OWL 온톨로지 데이터 생성기
# =============================================================================
# Neo4j에 로드하기 위한 OWL 형식의 WMS 온톨로지 데이터를 생성합니다.
#
# 온톨로지 스키마:
#   Classes:
#     - Organization (조직): 창고 운영 조직
#     - Warehouse (창고): 물류 보관 시설
#     - Zone (구역): 창고 내 기능별 구역
#     - Bin (로케이션): 재고 보관 위치 (행-열-레벨)
#     - InventoryItem (재고 품목): 창고에 보관된 재고
#     - InboundOrder (입고 오더): 입고 예정/완료 오더
#     - OutboundOrder (출고 오더): 출고 예정/완료 오더
#
#   Relationships:
#     - BELONGS_TO: Zone → Warehouse
#     - LOCATED_IN: Bin → Zone
#     - STORED_AT: InventoryItem → Bin
#     - INBOUND_TO: InboundOrder → Warehouse
#     - OUTBOUND_FROM: OutboundOrder → Warehouse
#     - CONTAINS_ITEM: InboundOrder/OutboundOrder → InventoryItem
#     - MANAGED_BY: Warehouse → Organization
#
# 실행 방법:
#   python -m genai-fundamentals.tools.generate_wms_owl
#   python -m genai-fundamentals.tools.generate_wms_owl [창고수] [입고수] [출고수]
#
# 출력:
#   - data/wms_ontology.owl (OWL 파일)
#   - data/wms_ontology.ttl (Turtle 형식)
# =============================================================================

import random
from datetime import datetime, timedelta
from pathlib import Path
from typing import List

try:
    from rdflib import Graph, Namespace, Literal, URIRef
    from rdflib.namespace import RDF, RDFS, OWL, XSD
except ImportError:
    print("=" * 60)
    print("오류: rdflib 라이브러리가 설치되어 있지 않습니다.")
    print()
    print("설치 방법:")
    print("  pip install rdflib")
    print("=" * 60)
    exit(1)

# =============================================================================
# 상수 및 네임스페이스 정의
# =============================================================================

WMS = Namespace("http://capora.ai/ontology/wms#")
WMSI = Namespace("http://capora.ai/ontology/wms/instance#")

# 창고 목록
WAREHOUSES = [
    ("WH_Incheon", "인천 물류센터", "인천광역시 중구 공항로 272", 5000, 15000),
    ("WH_Busan", "부산 물류센터", "부산광역시 남구 감만동", 8000, 24000),
    ("WH_Pyeongtaek", "평택 물류센터", "경기도 평택시 포승읍", 6000, 18000),
    ("WH_Gwangyang", "광양 물류센터", "전라남도 광양시 광양읍", 4000, 12000),
    ("WH_Seoul", "서울 강서 물류센터", "서울특별시 강서구 마곡동", 3000, 9000),
    ("WH_Daejeon", "대전 물류센터", "대전광역시 유성구 노은동", 3500, 10500),
    ("WH_Daegu", "대구 물류센터", "대구광역시 달서구 장동", 4500, 13500),
    ("WH_Gwangju", "광주 물류센터", "광주광역시 광산구 하남동", 3000, 9000),
    ("WH_Sejong", "세종 물류센터", "세종특별자치시 연기면", 2500, 7500),
    ("WH_Icheon", "이천 물류센터", "경기도 이천시 호법면", 7000, 21000),
]

# 구역 유형
ZONE_TYPES = [
    ("inbound", "입고존"),
    ("storage", "보관존"),
    ("outbound", "출고존"),
    ("picking", "피킹존"),
]

# SKU 카테고리
SKU_CATEGORIES = [
    ("ELC", "전자제품"),
    ("FUD", "식품"),
    ("CLO", "의류"),
    ("CHM", "화학물질"),
    ("AUT", "자동차부품"),
    ("MED", "의약품"),
    ("BLD", "건축자재"),
    ("AGR", "농산물"),
    ("FSH", "수산물"),
    ("HOM", "가정용품"),
]

# 입고 상태
INBOUND_STATUSES = ["scheduled", "arrived", "receiving", "completed", "cancelled"]
INBOUND_STATUS_WEIGHTS = [15, 10, 10, 55, 10]

# 출고 상태
OUTBOUND_STATUSES = ["pending", "picking", "packed", "shipped", "cancelled"]
OUTBOUND_STATUS_WEIGHTS = [15, 10, 10, 55, 10]

# 운영 조직
ORGANIZATION_NAMES = [
    "CJ대한통운 물류센터", "롯데글로벌로지스", "한진로지스틱스",
    "현대글로비스", "삼성SDS 물류", "쿠팡 풀필먼트",
    "마켓컬리 물류", "SSG닷컴 물류", "네이버 물류센터",
    "카카오 물류", "GS리테일 물류", "풀무원 물류센터",
]


# =============================================================================
# OWL 온톨로지 생성 클래스
# =============================================================================

class WMSOntologyGenerator:
    """WMS (Warehouse Management System) OWL 온톨로지 생성기"""

    def __init__(self):
        self.graph = Graph()
        self.graph.bind("wms", WMS)
        self.graph.bind("wmsi", WMSI)
        self.graph.bind("owl", OWL)
        self.graph.bind("rdfs", RDFS)
        self.graph.bind("xsd", XSD)

        self.organizations: List[URIRef] = []
        self.warehouses: List[URIRef] = []
        self.zones: List[URIRef] = []
        self.bins: List[URIRef] = []
        self.inventory_items: List[URIRef] = []
        self.inbound_orders: List[URIRef] = []
        self.outbound_orders: List[URIRef] = []

        # 창고별 빈 목록 (적재율 계산용)
        self._warehouse_bins: dict = {}

    def create_ontology_schema(self):
        """온톨로지 스키마 (TBox) 생성"""
        print("📋 WMS 온톨로지 스키마 생성 중...")

        ontology_uri = URIRef("http://capora.ai/ontology/wms")
        self.graph.add((ontology_uri, RDF.type, OWL.Ontology))
        self.graph.add((ontology_uri, RDFS.label, Literal("WMS Ontology", lang="en")))
        self.graph.add((ontology_uri, RDFS.label, Literal("창고 관리 시스템 온톨로지", lang="ko")))
        self.graph.add((ontology_uri, RDFS.comment, Literal(
            "창고, 구역, 로케이션, 재고, 입출고를 관리하는 온톨로지", lang="ko")))
        self.graph.add((ontology_uri, OWL.versionInfo, Literal("1.0.0")))

        # Classes
        classes = [
            (WMS.Organization, "Organization", "조직", "창고 운영 조직"),
            (WMS.Warehouse, "Warehouse", "창고", "물류 보관 시설"),
            (WMS.Zone, "Zone", "구역", "창고 내 기능별 구역"),
            (WMS.Bin, "Bin", "로케이션", "재고 보관 위치 (행-열-레벨)"),
            (WMS.InventoryItem, "InventoryItem", "재고품목", "창고에 보관된 재고"),
            (WMS.InboundOrder, "InboundOrder", "입고오더", "입고 예정/완료 오더"),
            (WMS.OutboundOrder, "OutboundOrder", "출고오더", "출고 예정/완료 오더"),
        ]

        for cls_uri, label_en, label_ko, comment_ko in classes:
            self.graph.add((cls_uri, RDF.type, OWL.Class))
            self.graph.add((cls_uri, RDFS.label, Literal(label_en, lang="en")))
            self.graph.add((cls_uri, RDFS.label, Literal(label_ko, lang="ko")))
            self.graph.add((cls_uri, RDFS.comment, Literal(comment_ko, lang="ko")))

        # Object Properties
        object_properties = [
            (WMS.belongsTo, "belongsTo", "소속창고", WMS.Zone, WMS.Warehouse,
             "구역이 속한 창고"),
            (WMS.locatedIn, "locatedIn", "위치구역", WMS.Bin, WMS.Zone,
             "로케이션이 위치한 구역"),
            (WMS.storedAt, "storedAt", "보관위치", WMS.InventoryItem, WMS.Bin,
             "재고가 보관된 로케이션"),
            (WMS.inboundTo, "inboundTo", "입고창고", WMS.InboundOrder, WMS.Warehouse,
             "입고 대상 창고"),
            (WMS.outboundFrom, "outboundFrom", "출고창고", WMS.OutboundOrder, WMS.Warehouse,
             "출고 창고"),
            (WMS.containsItem, "containsItem", "포함품목", None, WMS.InventoryItem,
             "오더에 포함된 품목"),
            (WMS.managedBy, "managedBy", "운영조직", WMS.Warehouse, WMS.Organization,
             "창고 운영 조직"),
        ]

        for prop_uri, label_en, label_ko, domain, range_, comment_ko in object_properties:
            self.graph.add((prop_uri, RDF.type, OWL.ObjectProperty))
            self.graph.add((prop_uri, RDFS.label, Literal(label_en, lang="en")))
            self.graph.add((prop_uri, RDFS.label, Literal(label_ko, lang="ko")))
            if domain:
                self.graph.add((prop_uri, RDFS.domain, domain))
            self.graph.add((prop_uri, RDFS.range, range_))
            self.graph.add((prop_uri, RDFS.comment, Literal(comment_ko, lang="ko")))

        # Data Properties
        data_properties = [
            (WMS.name, "name", "이름", XSD.string),
            (WMS.address, "address", "주소", XSD.string),
            (WMS.warehouseId, "warehouseId", "창고ID", XSD.string),
            (WMS.capacityM2, "capacityM2", "면적(m2)", XSD.decimal),
            (WMS.capacityM3, "capacityM3", "용적(m3)", XSD.decimal),
            (WMS.zoneId, "zoneId", "구역ID", XSD.string),
            (WMS.zoneType, "zoneType", "구역유형", XSD.string),
            (WMS.capacity, "capacity", "용량", XSD.integer),
            (WMS.binId, "binId", "빈ID", XSD.string),
            (WMS.row, "row", "행", XSD.integer),
            (WMS.column, "column", "열", XSD.integer),
            (WMS.level, "level", "레벨", XSD.integer),
            (WMS.status, "status", "상태", XSD.string),
            (WMS.sku, "sku", "SKU", XSD.string),
            (WMS.quantity, "quantity", "수량", XSD.integer),
            (WMS.lotNumber, "lotNumber", "로트번호", XSD.string),
            (WMS.expiryDate, "expiryDate", "유효기한", XSD.date),
            (WMS.lastUpdated, "lastUpdated", "최종수정일", XSD.dateTime),
            (WMS.inboundId, "inboundId", "입고ID", XSD.string),
            (WMS.outboundId, "outboundId", "출고ID", XSD.string),
            (WMS.expectedDate, "expectedDate", "예정일", XSD.date),
            (WMS.actualDate, "actualDate", "실제일", XSD.date),
            (WMS.destination, "destination", "목적지", XSD.string),
            (WMS.skuCategory, "skuCategory", "SKU카테고리", XSD.string),
        ]

        for prop_uri, label_en, label_ko, datatype in data_properties:
            self.graph.add((prop_uri, RDF.type, OWL.DatatypeProperty))
            self.graph.add((prop_uri, RDFS.label, Literal(label_en, lang="en")))
            self.graph.add((prop_uri, RDFS.label, Literal(label_ko, lang="ko")))
            self.graph.add((prop_uri, RDFS.range, datatype))

        print(f"   클래스 7개, Object Property 7개, Data Property {len(data_properties)}개 생성")

    def create_organizations(self):
        """조직 인스턴스 생성"""
        print(f"🏢 조직 {len(ORGANIZATION_NAMES)}개 생성 중...")

        for i, org_name in enumerate(ORGANIZATION_NAMES):
            uri = WMSI[f"Org_{i+1:03d}"]
            self.graph.add((uri, RDF.type, WMS.Organization))
            self.graph.add((uri, WMS.name, Literal(org_name, lang="ko")))
            self.organizations.append(uri)

        print(f"   조직 {len(ORGANIZATION_NAMES)}개 생성 완료")

    def create_warehouses(self, count: int = 10):
        """창고 인스턴스 생성 (구역 + 빈 포함)"""
        actual_count = min(count, len(WAREHOUSES))
        print(f"🏭 창고 {actual_count}개 생성 중 (구역, 로케이션 포함)...")

        total_zones = 0
        total_bins = 0

        for i in range(actual_count):
            wh_id, wh_name, address, cap_m2, cap_m3 = WAREHOUSES[i]
            wh_uri = WMSI[wh_id]

            self.graph.add((wh_uri, RDF.type, WMS.Warehouse))
            self.graph.add((wh_uri, WMS.warehouseId, Literal(wh_id)))
            self.graph.add((wh_uri, WMS.name, Literal(wh_name, lang="ko")))
            self.graph.add((wh_uri, WMS.address, Literal(address, lang="ko")))
            self.graph.add((wh_uri, WMS.capacityM2, Literal(cap_m2, datatype=XSD.decimal)))
            self.graph.add((wh_uri, WMS.capacityM3, Literal(cap_m3, datatype=XSD.decimal)))

            # MANAGED_BY
            org = random.choice(self.organizations)
            self.graph.add((wh_uri, WMS.managedBy, org))

            self.warehouses.append(wh_uri)
            self._warehouse_bins[wh_id] = []

            # 구역 생성 (창고당 4개 구역)
            for zt_id, zt_name in ZONE_TYPES:
                zone_id = f"{wh_id}_{zt_id}"
                zone_uri = WMSI[zone_id]

                zone_capacity = random.randint(50, 200)

                self.graph.add((zone_uri, RDF.type, WMS.Zone))
                self.graph.add((zone_uri, WMS.zoneId, Literal(zone_id)))
                self.graph.add((zone_uri, WMS.zoneType, Literal(zt_id)))
                self.graph.add((zone_uri, WMS.name, Literal(f"{wh_name} {zt_name}", lang="ko")))
                self.graph.add((zone_uri, WMS.capacity, Literal(zone_capacity, datatype=XSD.integer)))
                self.graph.add((zone_uri, WMS.belongsTo, wh_uri))

                self.zones.append(zone_uri)
                total_zones += 1

                # 빈 생성 (구역당 행3~5 × 열5~10 × 레벨2~4)
                max_rows = random.randint(3, 5)
                max_cols = random.randint(5, 10)
                max_levels = random.randint(2, 4)

                for r in range(1, max_rows + 1):
                    for c in range(1, max_cols + 1):
                        for lv in range(1, max_levels + 1):
                            bin_id = f"{zone_id}_R{r:02d}C{c:02d}L{lv}"
                            bin_uri = WMSI[bin_id]

                            bin_status = random.choices(
                                ["empty", "occupied", "reserved"],
                                weights=[30, 55, 15], k=1
                            )[0]

                            self.graph.add((bin_uri, RDF.type, WMS.Bin))
                            self.graph.add((bin_uri, WMS.binId, Literal(bin_id)))
                            self.graph.add((bin_uri, WMS.row, Literal(r, datatype=XSD.integer)))
                            self.graph.add((bin_uri, WMS.column, Literal(c, datatype=XSD.integer)))
                            self.graph.add((bin_uri, WMS.level, Literal(lv, datatype=XSD.integer)))
                            self.graph.add((bin_uri, WMS.status, Literal(bin_status)))
                            self.graph.add((bin_uri, WMS.locatedIn, zone_uri))

                            self.bins.append(bin_uri)
                            self._warehouse_bins[wh_id].append((bin_uri, bin_status))
                            total_bins += 1

        print(f"   창고 {actual_count}개, 구역 {total_zones}개, 로케이션 {total_bins}개 생성 완료")

    def create_inventory_items(self):
        """재고 품목 생성 (occupied 빈에 재고 배치)"""
        print("📦 재고 품목 생성 중...")

        item_idx = 0
        for bin_uri, bin_status in [(b, s) for bins in self._warehouse_bins.values() for b, s in bins]:
            if bin_status != "occupied":
                continue

            item_idx += 1
            item_id = f"INV_{item_idx:05d}"
            uri = WMSI[item_id]

            cat_code, cat_name = random.choice(SKU_CATEGORIES)
            sku = f"{cat_code}-{random.randint(10000, 99999)}"
            quantity = random.randint(1, 500)
            lot = f"LOT-{random.randint(100000, 999999)}"
            updated = datetime.now() - timedelta(days=random.randint(0, 30))

            self.graph.add((uri, RDF.type, WMS.InventoryItem))
            self.graph.add((uri, WMS.sku, Literal(sku)))
            self.graph.add((uri, WMS.skuCategory, Literal(cat_name, lang="ko")))
            self.graph.add((uri, WMS.quantity, Literal(quantity, datatype=XSD.integer)))
            self.graph.add((uri, WMS.lotNumber, Literal(lot)))
            self.graph.add((uri, WMS.lastUpdated, Literal(
                updated.isoformat(), datatype=XSD.dateTime)))

            # 유효기한 (식품/의약품만)
            if cat_code in ("FUD", "MED", "AGR", "FSH"):
                expiry = datetime.now() + timedelta(days=random.randint(30, 365))
                self.graph.add((uri, WMS.expiryDate, Literal(
                    expiry.strftime("%Y-%m-%d"), datatype=XSD.date)))

            # STORED_AT
            self.graph.add((uri, WMS.storedAt, bin_uri))
            self.inventory_items.append(uri)

        print(f"   재고 품목 {item_idx}건 생성 완료")

    def create_inbound_orders(self, count: int = 100):
        """입고 오더 생성"""
        print(f"📥 입고 오더 {count}건 생성 중...")

        for i in range(count):
            ib_id = f"IB_{i+1:04d}"
            uri = WMSI[ib_id]

            status = random.choices(INBOUND_STATUSES, weights=INBOUND_STATUS_WEIGHTS, k=1)[0]
            expected = datetime.now() + timedelta(days=random.randint(-10, 30))
            warehouse = random.choice(self.warehouses)

            self.graph.add((uri, RDF.type, WMS.InboundOrder))
            self.graph.add((uri, WMS.inboundId, Literal(ib_id)))
            self.graph.add((uri, WMS.status, Literal(status)))
            self.graph.add((uri, WMS.expectedDate, Literal(
                expected.strftime("%Y-%m-%d"), datatype=XSD.date)))
            self.graph.add((uri, WMS.inboundTo, warehouse))

            if status in ("completed", "receiving"):
                actual = expected - timedelta(days=random.randint(0, 2))
                self.graph.add((uri, WMS.actualDate, Literal(
                    actual.strftime("%Y-%m-%d"), datatype=XSD.date)))

            # CONTAINS_ITEM (1~5개)
            if self.inventory_items:
                num_items = random.randint(1, min(5, len(self.inventory_items)))
                items = random.sample(self.inventory_items, k=num_items)
                for item in items:
                    self.graph.add((uri, WMS.containsItem, item))

            self.inbound_orders.append(uri)

        print(f"   입고 오더 {count}건 생성 완료")

    def create_outbound_orders(self, count: int = 150):
        """출고 오더 생성"""
        print(f"📤 출고 오더 {count}건 생성 중...")

        destinations = [
            "서울 강남구", "부산 해운대구", "인천 남동구", "대구 수성구",
            "광주 서구", "대전 유성구", "울산 남구", "경기 수원시",
            "경기 성남시", "충남 천안시", "전북 전주시", "경남 창원시",
        ]

        for i in range(count):
            ob_id = f"OB_{i+1:04d}"
            uri = WMSI[ob_id]

            status = random.choices(OUTBOUND_STATUSES, weights=OUTBOUND_STATUS_WEIGHTS, k=1)[0]
            expected = datetime.now() + timedelta(days=random.randint(-5, 14))
            warehouse = random.choice(self.warehouses)

            self.graph.add((uri, RDF.type, WMS.OutboundOrder))
            self.graph.add((uri, WMS.outboundId, Literal(ob_id)))
            self.graph.add((uri, WMS.status, Literal(status)))
            self.graph.add((uri, WMS.expectedDate, Literal(
                expected.strftime("%Y-%m-%d"), datatype=XSD.date)))
            self.graph.add((uri, WMS.destination, Literal(
                random.choice(destinations), lang="ko")))
            self.graph.add((uri, WMS.outboundFrom, warehouse))

            if status == "shipped":
                actual = expected - timedelta(days=random.randint(0, 1))
                self.graph.add((uri, WMS.actualDate, Literal(
                    actual.strftime("%Y-%m-%d"), datatype=XSD.date)))

            # CONTAINS_ITEM (1~3개)
            if self.inventory_items:
                num_items = random.randint(1, min(3, len(self.inventory_items)))
                items = random.sample(self.inventory_items, k=num_items)
                for item in items:
                    self.graph.add((uri, WMS.containsItem, item))

            self.outbound_orders.append(uri)

        print(f"   출고 오더 {count}건 생성 완료")

    def save(self, output_dir: str = "data"):
        """온톨로지를 파일로 저장"""
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        owl_file = output_path / "wms_ontology.owl"
        self.graph.serialize(destination=str(owl_file), format="xml")
        print(f"💾 OWL 파일 저장: {owl_file}")

        ttl_file = output_path / "wms_ontology.ttl"
        self.graph.serialize(destination=str(ttl_file), format="turtle")
        print(f"💾 Turtle 파일 저장: {ttl_file}")

        print()
        print("📊 생성된 온톨로지 통계:")
        print(f"   - 총 트리플 수: {len(self.graph):,}개")
        print(f"   - 조직 (Organization): {len(self.organizations)}개")
        print(f"   - 창고 (Warehouse): {len(self.warehouses)}개")
        print(f"   - 구역 (Zone): {len(self.zones)}개")
        print(f"   - 로케이션 (Bin): {len(self.bins)}개")
        print(f"   - 재고품목 (InventoryItem): {len(self.inventory_items)}개")
        print(f"   - 입고오더 (InboundOrder): {len(self.inbound_orders)}건")
        print(f"   - 출고오더 (OutboundOrder): {len(self.outbound_orders)}건")

        return owl_file, ttl_file

    def generate(self, warehouse_count: int = 10, inbound_count: int = 100,
                 outbound_count: int = 150):
        """전체 온톨로지 생성"""
        print("=" * 60)
        print("WMS (Warehouse Management System) OWL 온톨로지 생성")
        print("=" * 60)
        print()

        self.create_ontology_schema()
        self.create_organizations()
        self.create_warehouses(warehouse_count)
        self.create_inventory_items()
        self.create_inbound_orders(inbound_count)
        self.create_outbound_orders(outbound_count)

        print()
        return self.save()


# =============================================================================
# 메인 실행
# =============================================================================

if __name__ == "__main__":
    import sys

    warehouse_count = 10
    inbound_count = 100
    outbound_count = 150

    if len(sys.argv) > 1:
        warehouse_count = int(sys.argv[1])
    if len(sys.argv) > 2:
        inbound_count = int(sys.argv[2])
    if len(sys.argv) > 3:
        outbound_count = int(sys.argv[3])

    generator = WMSOntologyGenerator()
    owl_file, ttl_file = generator.generate(
        warehouse_count=warehouse_count,
        inbound_count=inbound_count,
        outbound_count=outbound_count
    )

    print()
    print("=" * 60)
    print("생성 완료!")
    print()
    print("다음 단계:")
    print("1. Neo4j에 로드:")
    print("   python -m genai-fundamentals.tools.owl_to_neo4j data/wms_ontology.ttl --clear")
    print()
    print("2. 온톨로지 확인:")
    print(f"   - {owl_file}")
    print(f"   - {ttl_file}")
    print("=" * 60)
