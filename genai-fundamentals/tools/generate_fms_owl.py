# =============================================================================
# FMS (Fleet Management System) OWL 온톨로지 데이터 생성기
# =============================================================================
# Neo4j에 로드하기 위한 OWL 형식의 FMS 온톨로지 데이터를 생성합니다.
#
# 온톨로지 스키마:
#   Classes:
#     - Organization (조직): 차량/운전자 소속 조직
#     - Vehicle (차량): 관리 대상 차량
#     - Driver (운전자): 차량 운전자
#     - MaintenanceRecord (정비 기록): 차량 정비 이력
#     - FuelRecord (주유 기록): 연료 주입 기록
#     - Consumable (소모품): 차량 소모품
#     - RiskScore (위험 점수): 차량/운전자 위험도 평가
#
#   Relationships:
#     - ASSIGNED_TO: Driver → Vehicle
#     - HAS_MAINTENANCE: Vehicle → MaintenanceRecord
#     - HAS_FUEL: Vehicle → FuelRecord
#     - HAS_CONSUMABLE: Vehicle → Consumable
#     - OWNED_BY: Vehicle → Organization
#     - EMPLOYED_BY: Driver → Organization
#     - HAS_RISK: Vehicle/Driver → RiskScore
#
# 실행 방법:
#   python -m genai-fundamentals.tools.generate_fms_owl
#   python -m genai-fundamentals.tools.generate_fms_owl [조직수] [차량수] [운전자수]
#
# 출력:
#   - data/fms_ontology.owl (OWL 파일)
#   - data/fms_ontology.ttl (Turtle 형식)
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

FMS = Namespace("http://capora.ai/ontology/fms#")
FMSI = Namespace("http://capora.ai/ontology/fms/instance#")

# 차량 유형 (type_id, 한국어명, 브랜드 목록)
VEHICLE_TYPES = [
    "1톤 트럭", "2.5톤 트럭", "5톤 트럭", "11톤 트럭", "25톤 트럭",
    "윙바디", "냉동/냉장차", "컨테이너", "탱크로리", "평판차",
]

VEHICLE_BRANDS = [
    ("현대", ["포터2", "마이티", "메가트럭", "엑시언트", "파비스"]),
    ("기아", ["봉고3", "K2500", "K3500"]),
    ("타타대우", ["노부스", "맥시머스", "프리마"]),
    ("만트럭", ["TGS", "TGX", "TGL"]),
    ("볼보", ["FH16", "FM", "FE"]),
    ("스카니아", ["R시리즈", "S시리즈", "P시리즈"]),
]

VEHICLE_STATUSES = ["active", "inactive", "maintenance", "retired"]
VEHICLE_STATUS_WEIGHTS = [60, 10, 20, 10]  # 확률 가중치

MAINTENANCE_TYPES = [
    ("regular", "정기점검"),
    ("repair", "수리"),
    ("inspection", "검사"),
    ("tire", "타이어 교체"),
    ("oil", "오일 교환"),
]

FUEL_TYPES = ["경유", "휘발유", "LPG", "전기", "수소"]

GAS_STATIONS = [
    "SK에너지", "GS칼텍스", "S-OIL", "현대오일뱅크",
    "알뜰주유소", "코스트코주유소",
]

CONSUMABLE_TYPES = [
    ("엔진오일", 10000),
    ("에어필터", 15000),
    ("브레이크패드", 30000),
    ("타이어", 50000),
    ("배터리", 60000),
    ("와이퍼 블레이드", 20000),
    ("냉각수", 40000),
    ("미션오일", 60000),
    ("브레이크 오일", 40000),
    ("연료필터", 20000),
]

CONSUMABLE_STATUSES = ["good", "warning", "replace_soon", "overdue"]
CONSUMABLE_STATUS_WEIGHTS = [50, 25, 15, 10]

RISK_FACTORS = [
    "과속 이력", "급제동 빈도", "정비 지연", "사고 이력", "운행 시간 초과",
    "연비 저하", "소모품 교체 지연", "차령 노후", "타이어 마모",
]

# 한국 이름 생성용
KOREAN_LAST_NAMES = ["김", "이", "박", "최", "정", "강", "조", "윤", "장", "임",
                     "한", "오", "서", "신", "권", "황", "안", "송", "류", "홍"]
KOREAN_FIRST_NAMES = ["민수", "지훈", "서연", "예진", "현우", "수진", "동현", "미영",
                      "준호", "유진", "성민", "은지", "태현", "소연", "재혁", "하늘"]

ORGANIZATION_NAMES = [
    "대한통운", "한진택배", "롯데글로벌", "CJ대한통운", "현대로지스틱스",
    "우체국택배", "로젠택배", "경동택배", "일양로지스", "천일택배",
    "합동화물", "건영물류", "대신택배", "동부익스프레스", "세방물류",
    "삼성SDS", "범한판토스", "흥아해운", "유성물류", "고려택배",
]


# =============================================================================
# 헬퍼 함수
# =============================================================================

def generate_korean_name() -> str:
    return random.choice(KOREAN_LAST_NAMES) + random.choice(KOREAN_FIRST_NAMES)


def generate_license_plate() -> str:
    regions = ["서울", "부산", "인천", "대구", "광주", "대전", "울산", "경기",
               "강원", "충북", "충남", "전북", "전남", "경북", "경남", "제주"]
    letters = "가나다라마바사아자차카타파하"
    return f"{random.choice(regions)}{random.choice(letters)}{random.randint(1000, 9999)}"


def generate_phone() -> str:
    return f"010-{random.randint(1000, 9999)}-{random.randint(1000, 9999)}"


def generate_license_number() -> str:
    """운전면허 번호 생성 (xx-xxxxxxxx-xx)"""
    region = random.randint(11, 26)
    seq = random.randint(10000000, 99999999)
    check = random.randint(10, 99)
    return f"{region}-{seq}-{check}"


# =============================================================================
# OWL 온톨로지 생성 클래스
# =============================================================================

class FMSOntologyGenerator:
    """FMS (Fleet Management System) OWL 온톨로지 생성기"""

    def __init__(self):
        self.graph = Graph()
        self.graph.bind("fms", FMS)
        self.graph.bind("fmsi", FMSI)
        self.graph.bind("owl", OWL)
        self.graph.bind("rdfs", RDFS)
        self.graph.bind("xsd", XSD)

        self.organizations: List[URIRef] = []
        self.vehicles: List[URIRef] = []
        self.drivers: List[URIRef] = []
        self.maintenance_records: List[URIRef] = []
        self.fuel_records: List[URIRef] = []
        self.consumables: List[URIRef] = []
        self.risk_scores: List[URIRef] = []

    def create_ontology_schema(self):
        """온톨로지 스키마 (TBox) 생성"""
        print("📋 FMS 온톨로지 스키마 생성 중...")

        ontology_uri = URIRef("http://capora.ai/ontology/fms")
        self.graph.add((ontology_uri, RDF.type, OWL.Ontology))
        self.graph.add((ontology_uri, RDFS.label, Literal("FMS Ontology", lang="en")))
        self.graph.add((ontology_uri, RDFS.label, Literal("차량 관리 시스템 온톨로지", lang="ko")))
        self.graph.add((ontology_uri, RDFS.comment, Literal(
            "차량, 운전자, 정비, 주유, 소모품, 위험도를 관리하는 온톨로지", lang="ko")))
        self.graph.add((ontology_uri, OWL.versionInfo, Literal("1.0.0")))

        # Classes
        classes = [
            (FMS.Organization, "Organization", "조직", "차량/운전자 소속 조직"),
            (FMS.Vehicle, "Vehicle", "차량", "관리 대상 차량"),
            (FMS.Driver, "Driver", "운전자", "차량 운전자"),
            (FMS.MaintenanceRecord, "MaintenanceRecord", "정비기록", "차량 정비 이력"),
            (FMS.FuelRecord, "FuelRecord", "주유기록", "연료 주입 기록"),
            (FMS.Consumable, "Consumable", "소모품", "차량 소모품 정보"),
            (FMS.RiskScore, "RiskScore", "위험점수", "차량/운전자 위험도 평가"),
        ]

        for cls_uri, label_en, label_ko, comment_ko in classes:
            self.graph.add((cls_uri, RDF.type, OWL.Class))
            self.graph.add((cls_uri, RDFS.label, Literal(label_en, lang="en")))
            self.graph.add((cls_uri, RDFS.label, Literal(label_ko, lang="ko")))
            self.graph.add((cls_uri, RDFS.comment, Literal(comment_ko, lang="ko")))

        # Object Properties
        object_properties = [
            (FMS.assignedTo, "assignedTo", "배정됨", FMS.Driver, FMS.Vehicle,
             "운전자가 차량에 배정됨"),
            (FMS.hasMaintenance, "hasMaintenance", "정비기록", FMS.Vehicle, FMS.MaintenanceRecord,
             "차량의 정비 기록"),
            (FMS.hasFuel, "hasFuel", "주유기록", FMS.Vehicle, FMS.FuelRecord,
             "차량의 주유 기록"),
            (FMS.hasConsumable, "hasConsumable", "소모품", FMS.Vehicle, FMS.Consumable,
             "차량에 장착된 소모품"),
            (FMS.ownedBy, "ownedBy", "소유조직", FMS.Vehicle, FMS.Organization,
             "차량 소유 조직"),
            (FMS.employedBy, "employedBy", "소속조직", FMS.Driver, FMS.Organization,
             "운전자 소속 조직"),
            (FMS.hasRisk, "hasRisk", "위험도", None, FMS.RiskScore,
             "위험도 평가 결과"),
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
            (FMS.name, "name", "이름", XSD.string),
            (FMS.vehicleId, "vehicleId", "차량ID", XSD.string),
            (FMS.licensePlate, "licensePlate", "차량번호", XSD.string),
            (FMS.vehicleType, "vehicleType", "차량유형", XSD.string),
            (FMS.brand, "brand", "브랜드", XSD.string),
            (FMS.model, "model", "모델", XSD.string),
            (FMS.year, "year", "연식", XSD.integer),
            (FMS.mileage, "mileage", "주행거리(km)", XSD.integer),
            (FMS.status, "status", "상태", XSD.string),
            (FMS.driverId, "driverId", "운전자ID", XSD.string),
            (FMS.licenseNumber, "licenseNumber", "면허번호", XSD.string),
            (FMS.licenseExpiry, "licenseExpiry", "면허만료일", XSD.date),
            (FMS.phone, "phone", "전화번호", XSD.string),
            (FMS.rating, "rating", "평점", XSD.decimal),
            (FMS.maintenanceId, "maintenanceId", "정비ID", XSD.string),
            (FMS.maintenanceType, "maintenanceType", "정비유형", XSD.string),
            (FMS.date, "date", "날짜", XSD.date),
            (FMS.cost, "cost", "비용(원)", XSD.decimal),
            (FMS.description, "description", "설명", XSD.string),
            (FMS.nextDueDate, "nextDueDate", "다음정비일", XSD.date),
            (FMS.fuelId, "fuelId", "주유ID", XSD.string),
            (FMS.amount, "amount", "주유량(L)", XSD.decimal),
            (FMS.fuelType, "fuelType", "연료유형", XSD.string),
            (FMS.station, "station", "주유소", XSD.string),
            (FMS.consumableId, "consumableId", "소모품ID", XSD.string),
            (FMS.installDate, "installDate", "장착일", XSD.date),
            (FMS.expectedLifeKm, "expectedLifeKm", "예상수명(km)", XSD.integer),
            (FMS.currentLifeKm, "currentLifeKm", "현재수명(km)", XSD.integer),
            (FMS.score, "score", "점수", XSD.decimal),
            (FMS.evaluationDate, "evaluationDate", "평가일", XSD.date),
            (FMS.factors, "factors", "위험요인", XSD.string),
        ]

        for prop_uri, label_en, label_ko, datatype in data_properties:
            self.graph.add((prop_uri, RDF.type, OWL.DatatypeProperty))
            self.graph.add((prop_uri, RDFS.label, Literal(label_en, lang="en")))
            self.graph.add((prop_uri, RDFS.label, Literal(label_ko, lang="ko")))
            self.graph.add((prop_uri, RDFS.range, datatype))

        print(f"   클래스 7개, Object Property 7개, Data Property {len(data_properties)}개 생성")

    def create_organizations(self, count: int = 20):
        """조직 인스턴스 생성"""
        print(f"🏢 조직 {count}개 생성 중...")

        for i in range(count):
            org_id = f"Org_{i+1:03d}"
            uri = FMSI[org_id]

            if i < len(ORGANIZATION_NAMES):
                org_name = ORGANIZATION_NAMES[i]
            else:
                org_name = f"{generate_korean_name()} 물류 {i+1}"

            self.graph.add((uri, RDF.type, FMS.Organization))
            self.graph.add((uri, FMS.name, Literal(org_name, lang="ko")))

            self.organizations.append(uri)

        print(f"   조직 {count}개 생성 완료")

    def create_vehicles(self, count: int = 200):
        """차량 인스턴스 생성"""
        print(f"🚛 차량 {count}대 생성 중...")

        for i in range(count):
            vehicle_id = f"Vehicle_{i+1:04d}"
            uri = FMSI[vehicle_id]

            brand_name, models = random.choice(VEHICLE_BRANDS)
            model_name = random.choice(models)
            vtype = random.choice(VEHICLE_TYPES)
            year = random.randint(2015, 2025)
            mileage = random.randint(5000, 500000)
            status = random.choices(VEHICLE_STATUSES, weights=VEHICLE_STATUS_WEIGHTS, k=1)[0]

            self.graph.add((uri, RDF.type, FMS.Vehicle))
            self.graph.add((uri, FMS.vehicleId, Literal(vehicle_id)))
            self.graph.add((uri, FMS.licensePlate, Literal(generate_license_plate())))
            self.graph.add((uri, FMS.vehicleType, Literal(vtype, lang="ko")))
            self.graph.add((uri, FMS.brand, Literal(brand_name, lang="ko")))
            self.graph.add((uri, FMS.model, Literal(model_name, lang="ko")))
            self.graph.add((uri, FMS.year, Literal(year, datatype=XSD.integer)))
            self.graph.add((uri, FMS.mileage, Literal(mileage, datatype=XSD.integer)))
            self.graph.add((uri, FMS.status, Literal(status)))

            # OWNED_BY 관계
            org = random.choice(self.organizations)
            self.graph.add((uri, FMS.ownedBy, org))

            self.vehicles.append(uri)

        print(f"   차량 {count}대 생성 완료")

    def create_drivers(self, count: int = 150):
        """운전자 인스턴스 생성"""
        print(f"👤 운전자 {count}명 생성 중...")

        for i in range(count):
            driver_id = f"Driver_{i+1:04d}"
            uri = FMSI[driver_id]

            name = generate_korean_name()
            expiry = datetime.now() + timedelta(days=random.randint(30, 1825))
            status = random.choice(["active", "inactive", "suspended"])
            rating = round(random.uniform(3.0, 5.0), 1)

            self.graph.add((uri, RDF.type, FMS.Driver))
            self.graph.add((uri, FMS.driverId, Literal(driver_id)))
            self.graph.add((uri, FMS.name, Literal(name, lang="ko")))
            self.graph.add((uri, FMS.licenseNumber, Literal(generate_license_number())))
            self.graph.add((uri, FMS.licenseExpiry, Literal(
                expiry.strftime("%Y-%m-%d"), datatype=XSD.date)))
            self.graph.add((uri, FMS.phone, Literal(generate_phone())))
            self.graph.add((uri, FMS.status, Literal(status)))
            self.graph.add((uri, FMS.rating, Literal(rating, datatype=XSD.decimal)))

            # EMPLOYED_BY 관계
            org = random.choice(self.organizations)
            self.graph.add((uri, FMS.employedBy, org))

            # ASSIGNED_TO 관계 (1~2대 차량)
            num_vehicles = random.randint(1, min(2, len(self.vehicles)))
            assigned = random.sample(self.vehicles, k=num_vehicles)
            for v in assigned:
                self.graph.add((uri, FMS.assignedTo, v))

            self.drivers.append(uri)

        print(f"   운전자 {count}명 생성 완료")

    def create_maintenance_records(self):
        """정비 기록 생성 (차량당 1~5건)"""
        print("🔧 정비 기록 생성 중...")

        record_idx = 0
        for vehicle in self.vehicles:
            num_records = random.randint(1, 5)
            vehicle_mileage_values = sorted(
                [random.randint(5000, 300000) for _ in range(num_records)]
            )

            for j in range(num_records):
                record_idx += 1
                rec_id = f"Maint_{record_idx:05d}"
                uri = FMSI[rec_id]

                mtype_id, mtype_name = random.choice(MAINTENANCE_TYPES)
                rec_date = datetime.now() - timedelta(days=random.randint(1, 365))
                cost = random.randint(50000, 3000000)
                next_due = rec_date + timedelta(days=random.randint(90, 365))

                self.graph.add((uri, RDF.type, FMS.MaintenanceRecord))
                self.graph.add((uri, FMS.maintenanceId, Literal(rec_id)))
                self.graph.add((uri, FMS.maintenanceType, Literal(mtype_id)))
                self.graph.add((uri, FMS.date, Literal(
                    rec_date.strftime("%Y-%m-%d"), datatype=XSD.date)))
                self.graph.add((uri, FMS.mileage, Literal(
                    vehicle_mileage_values[j], datatype=XSD.integer)))
                self.graph.add((uri, FMS.cost, Literal(cost, datatype=XSD.decimal)))
                self.graph.add((uri, FMS.description, Literal(
                    f"{mtype_name} 수행", lang="ko")))
                self.graph.add((uri, FMS.nextDueDate, Literal(
                    next_due.strftime("%Y-%m-%d"), datatype=XSD.date)))

                # HAS_MAINTENANCE 관계
                self.graph.add((vehicle, FMS.hasMaintenance, uri))
                self.maintenance_records.append(uri)

        print(f"   정비 기록 {record_idx}건 생성 완료")

    def create_fuel_records(self):
        """주유 기록 생성 (차량당 3~10건)"""
        print("⛽ 주유 기록 생성 중...")

        record_idx = 0
        for vehicle in self.vehicles:
            num_records = random.randint(3, 10)
            fuel_type = random.choices(
                FUEL_TYPES, weights=[60, 10, 15, 10, 5], k=1
            )[0]

            base_mileage = random.randint(5000, 200000)
            for j in range(num_records):
                record_idx += 1
                fuel_id = f"Fuel_{record_idx:05d}"
                uri = FMSI[fuel_id]

                rec_date = datetime.now() - timedelta(days=random.randint(1, 180))
                amount = round(random.uniform(30, 200), 1)
                cost_per_liter = random.uniform(1500, 2200) if fuel_type != "전기" else random.uniform(200, 400)
                cost = round(amount * cost_per_liter)
                mileage = base_mileage + (j * random.randint(500, 2000))

                self.graph.add((uri, RDF.type, FMS.FuelRecord))
                self.graph.add((uri, FMS.fuelId, Literal(fuel_id)))
                self.graph.add((uri, FMS.date, Literal(
                    rec_date.strftime("%Y-%m-%d"), datatype=XSD.date)))
                self.graph.add((uri, FMS.amount, Literal(amount, datatype=XSD.decimal)))
                self.graph.add((uri, FMS.cost, Literal(cost, datatype=XSD.decimal)))
                self.graph.add((uri, FMS.mileage, Literal(mileage, datatype=XSD.integer)))
                self.graph.add((uri, FMS.fuelType, Literal(fuel_type, lang="ko")))
                self.graph.add((uri, FMS.station, Literal(
                    random.choice(GAS_STATIONS), lang="ko")))

                # HAS_FUEL 관계
                self.graph.add((vehicle, FMS.hasFuel, uri))
                self.fuel_records.append(uri)

        print(f"   주유 기록 {record_idx}건 생성 완료")

    def create_consumables(self):
        """소모품 생성 (차량당 3~6종)"""
        print("🔩 소모품 데이터 생성 중...")

        record_idx = 0
        for vehicle in self.vehicles:
            num_consumables = random.randint(3, 6)
            selected = random.sample(CONSUMABLE_TYPES, k=num_consumables)

            for cname, expected_km in selected:
                record_idx += 1
                cid = f"Cons_{record_idx:05d}"
                uri = FMSI[cid]

                install_date = datetime.now() - timedelta(days=random.randint(30, 365))
                current_km = random.randint(0, int(expected_km * 1.3))
                ratio = current_km / expected_km
                if ratio < 0.6:
                    status = "good"
                elif ratio < 0.8:
                    status = "warning"
                elif ratio <= 1.0:
                    status = "replace_soon"
                else:
                    status = "overdue"

                self.graph.add((uri, RDF.type, FMS.Consumable))
                self.graph.add((uri, FMS.consumableId, Literal(cid)))
                self.graph.add((uri, FMS.name, Literal(cname, lang="ko")))
                self.graph.add((uri, FMS.installDate, Literal(
                    install_date.strftime("%Y-%m-%d"), datatype=XSD.date)))
                self.graph.add((uri, FMS.expectedLifeKm, Literal(
                    expected_km, datatype=XSD.integer)))
                self.graph.add((uri, FMS.currentLifeKm, Literal(
                    current_km, datatype=XSD.integer)))
                self.graph.add((uri, FMS.status, Literal(status)))

                # HAS_CONSUMABLE 관계
                self.graph.add((vehicle, FMS.hasConsumable, uri))
                self.consumables.append(uri)

        print(f"   소모품 {record_idx}건 생성 완료")

    def create_risk_scores(self):
        """위험 점수 생성 (차량 + 운전자)"""
        print("⚠️  위험도 평가 생성 중...")

        record_idx = 0

        # 차량 위험도
        for vehicle in self.vehicles:
            record_idx += 1
            rid = f"Risk_{record_idx:05d}"
            uri = FMSI[rid]

            score = round(random.uniform(0, 100), 1)
            eval_date = datetime.now() - timedelta(days=random.randint(1, 90))
            num_factors = random.randint(0, 3)
            factors = random.sample(RISK_FACTORS, k=num_factors) if num_factors > 0 else []

            self.graph.add((uri, RDF.type, FMS.RiskScore))
            self.graph.add((uri, FMS.score, Literal(score, datatype=XSD.decimal)))
            self.graph.add((uri, FMS.evaluationDate, Literal(
                eval_date.strftime("%Y-%m-%d"), datatype=XSD.date)))
            self.graph.add((uri, FMS.factors, Literal(", ".join(factors) if factors else "없음")))

            self.graph.add((vehicle, FMS.hasRisk, uri))
            self.risk_scores.append(uri)

        # 운전자 위험도
        for driver in self.drivers:
            record_idx += 1
            rid = f"Risk_{record_idx:05d}"
            uri = FMSI[rid]

            score = round(random.uniform(0, 100), 1)
            eval_date = datetime.now() - timedelta(days=random.randint(1, 90))
            num_factors = random.randint(0, 3)
            factors = random.sample(RISK_FACTORS, k=num_factors) if num_factors > 0 else []

            self.graph.add((uri, RDF.type, FMS.RiskScore))
            self.graph.add((uri, FMS.score, Literal(score, datatype=XSD.decimal)))
            self.graph.add((uri, FMS.evaluationDate, Literal(
                eval_date.strftime("%Y-%m-%d"), datatype=XSD.date)))
            self.graph.add((uri, FMS.factors, Literal(", ".join(factors) if factors else "없음")))

            self.graph.add((driver, FMS.hasRisk, uri))
            self.risk_scores.append(uri)

        print(f"   위험도 평가 {record_idx}건 생성 완료 (차량 {len(self.vehicles)}건 + 운전자 {len(self.drivers)}건)")

    def save(self, output_dir: str = "data"):
        """온톨로지를 파일로 저장"""
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        owl_file = output_path / "fms_ontology.owl"
        self.graph.serialize(destination=str(owl_file), format="xml")
        print(f"💾 OWL 파일 저장: {owl_file}")

        ttl_file = output_path / "fms_ontology.ttl"
        self.graph.serialize(destination=str(ttl_file), format="turtle")
        print(f"💾 Turtle 파일 저장: {ttl_file}")

        print()
        print("📊 생성된 온톨로지 통계:")
        print(f"   - 총 트리플 수: {len(self.graph):,}개")
        print(f"   - 조직 (Organization): {len(self.organizations)}개")
        print(f"   - 차량 (Vehicle): {len(self.vehicles)}대")
        print(f"   - 운전자 (Driver): {len(self.drivers)}명")
        print(f"   - 정비기록 (MaintenanceRecord): {len(self.maintenance_records)}건")
        print(f"   - 주유기록 (FuelRecord): {len(self.fuel_records)}건")
        print(f"   - 소모품 (Consumable): {len(self.consumables)}건")
        print(f"   - 위험점수 (RiskScore): {len(self.risk_scores)}건")

        return owl_file, ttl_file

    def generate(self, org_count: int = 20, vehicle_count: int = 200, driver_count: int = 150):
        """전체 온톨로지 생성"""
        print("=" * 60)
        print("FMS (Fleet Management System) OWL 온톨로지 생성")
        print("=" * 60)
        print()

        self.create_ontology_schema()
        self.create_organizations(org_count)
        self.create_vehicles(vehicle_count)
        self.create_drivers(driver_count)
        self.create_maintenance_records()
        self.create_fuel_records()
        self.create_consumables()
        self.create_risk_scores()

        print()
        return self.save()


# =============================================================================
# 메인 실행
# =============================================================================

if __name__ == "__main__":
    import sys

    org_count = 20
    vehicle_count = 200
    driver_count = 150

    if len(sys.argv) > 1:
        org_count = int(sys.argv[1])
    if len(sys.argv) > 2:
        vehicle_count = int(sys.argv[2])
    if len(sys.argv) > 3:
        driver_count = int(sys.argv[3])

    generator = FMSOntologyGenerator()
    owl_file, ttl_file = generator.generate(
        org_count=org_count,
        vehicle_count=vehicle_count,
        driver_count=driver_count
    )

    print()
    print("=" * 60)
    print("생성 완료!")
    print()
    print("다음 단계:")
    print("1. Neo4j에 로드:")
    print("   python -m genai-fundamentals.tools.owl_to_neo4j data/fms_ontology.ttl --clear")
    print()
    print("2. 온톨로지 확인:")
    print(f"   - {owl_file}")
    print(f"   - {ttl_file}")
    print("=" * 60)
