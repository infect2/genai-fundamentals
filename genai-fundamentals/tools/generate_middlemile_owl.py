# =============================================================================
# Middlemile 물류 시스템 OWL 온톨로지 데이터 생성기
# =============================================================================
# Neo4j에 로드하기 위한 OWL 형식의 Middlemile 물류 온톨로지 데이터를 생성합니다.
#
# 온톨로지 스키마:
#   Classes:
#     - Shipper (화주): 화물을 보내는 기업/개인
#     - Carrier (운송사): 운송 서비스를 제공하는 기업
#     - Vehicle (차량): 운송사가 보유한 차량
#     - Cargo (화물): 운송 대상 물품
#     - Location (위치): 물류센터, 항구 등의 상위 클래스
#       - LogisticsCenter (물류센터)
#       - Port (항구)
#     - Shipment (배송): 배송 요청/진행 건
#     - MatchingService (매칭 서비스): 화주-운송사 매칭
#     - PricingService (가격 책정 서비스): 동적 가격 책정
#     - ConsolidationService (합적 서비스): 화물 합적
#
#   Object Properties:
#     - owns: Shipper → Cargo (화주가 화물 소유)
#     - operates: Carrier → Vehicle (운송사가 차량 운영)
#     - assignedTo: Shipment → Vehicle (배송에 차량 배정)
#     - contains: Shipment → Cargo (배송에 화물 포함)
#     - origin: Shipment → Location (출발지)
#     - destination: Shipment → Location (목적지)
#     - requestedBy: Shipment → Shipper (배송 요청자)
#     - fulfilledBy: Shipment → Carrier (배송 수행자)
#     - matches: MatchingService → (Shipper, Carrier) (매칭 결과)
#     - consolidates: ConsolidationService → Cargo (합적 화물)
#     - prices: PricingService → Shipment (가격 책정 대상)
#     - locatedAt: Carrier → Location (운송사 위치)
#
#   Data Properties:
#     - name, businessNumber, contactEmail (Shipper, Carrier)
#     - vehicleType, licensePlate, capacity (Vehicle)
#     - weight, volume, cargoType (Cargo)
#     - status, createdAt, estimatedDelivery (Shipment)
#     - price, currency (PricingService)
#     - latitude, longitude, address (Location)
#
# 실행 방법:
#   python -m genai-fundamentals.tools.generate_middlemile_owl
#
# 출력:
#   - data/middlemile_ontology.owl (OWL 파일)
#   - data/middlemile_ontology.ttl (Turtle 형식)
# =============================================================================

import random
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Tuple

try:
    from rdflib import Graph, Namespace, Literal, URIRef, BNode
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

# 온톨로지 네임스페이스
MM = Namespace("http://capora.ai/ontology/middlemile#")
MMI = Namespace("http://capora.ai/ontology/middlemile/instance#")

# 대한민국 주요 물류센터 위치
LOGISTICS_CENTERS = [
    ("LC_Incheon", "인천 물류센터", "인천광역시 중구 공항로 272", 37.4602, 126.4407),
    ("LC_Busan_Gamman", "부산 감만 물류센터", "부산광역시 남구 감만동", 35.0796, 129.0756),
    ("LC_Busan_Sinseondae", "부산 신선대 물류센터", "부산광역시 남구 신선로", 35.0689, 129.0847),
    ("LC_Pyeongtaek", "평택 물류센터", "경기도 평택시 포승읍", 36.9609, 126.9167),
    ("LC_Gwangyang", "광양 물류센터", "전라남도 광양시 광양읍", 34.9407, 127.6957),
    ("LC_Ulsan", "울산 물류센터", "울산광역시 남구 매암동", 35.5082, 129.3780),
    ("LC_Gunsan", "군산 물류센터", "전라북도 군산시 소룡동", 35.9837, 126.7180),
    ("LC_Mokpo", "목포 물류센터", "전라남도 목포시 대양동", 34.7879, 126.3923),
    ("LC_Donghae", "동해 물류센터", "강원도 동해시 송정동", 37.5045, 129.1245),
    ("LC_Seoul_Gangseo", "서울 강서 물류센터", "서울특별시 강서구 마곡동", 37.5665, 126.8372),
    ("LC_Daejeon", "대전 물류센터", "대전광역시 유성구 노은동", 36.3744, 127.3289),
    ("LC_Daegu", "대구 물류센터", "대구광역시 달서구 장동", 35.8303, 128.5324),
    ("LC_Gwangju", "광주 물류센터", "광주광역시 광산구 하남동", 35.1875, 126.8339),
    ("LC_Sejong", "세종 물류센터", "세종특별자치시 연기면", 36.5040, 127.2494),
    ("LC_Icheon", "이천 물류센터", "경기도 이천시 호법면", 37.2729, 127.4350),
]

# 대한민국 주요 항구
PORTS = [
    ("Port_Busan", "부산항", "부산광역시 중구 충장대로", 35.1028, 129.0403),
    ("Port_Incheon", "인천항", "인천광역시 중구 연안부두로", 37.4563, 126.5963),
    ("Port_Ulsan", "울산항", "울산광역시 남구 매암동", 35.4966, 129.3818),
    ("Port_Gwangyang", "광양항", "전라남도 광양시 광양읍", 34.9167, 127.7000),
    ("Port_Pyeongtaek", "평택항", "경기도 평택시 포승읍", 36.9675, 126.8230),
    ("Port_Gunsan", "군산항", "전라북도 군산시 소룡동", 35.9833, 126.7167),
    ("Port_Mokpo", "목포항", "전라남도 목포시 해안로", 34.7936, 126.3811),
    ("Port_Donghae", "동해항", "강원도 동해시 송정동", 37.4997, 129.1144),
    ("Port_Pohang", "포항항", "경상북도 포항시 남구 송도동", 36.0190, 129.3650),
    ("Port_Masan", "마산항", "경상남도 창원시 마산합포구", 35.1833, 128.5667),
]

# 차량 유형
VEHICLE_TYPES = [
    ("1t_truck", "1톤 트럭", 1000, 3.5),
    ("2.5t_truck", "2.5톤 트럭", 2500, 8.5),
    ("5t_truck", "5톤 트럭", 5000, 17.0),
    ("11t_truck", "11톤 트럭", 11000, 36.0),
    ("25t_truck", "25톤 트럭", 25000, 65.0),
    ("wing_body", "윙바디", 15000, 50.0),
    ("refrigerated", "냉동/냉장차", 8000, 28.0),
    ("container", "컨테이너", 20000, 60.0),
    ("tanker", "탱크로리", 18000, 30.0),
    ("flatbed", "평판차", 12000, 40.0),
]

# 화물 유형
CARGO_TYPES = [
    "일반화물",
    "냉동화물",
    "냉장화물",
    "위험물",
    "중량물",
    "정밀기기",
    "식품",
    "의약품",
    "전자제품",
    "건축자재",
    "농산물",
    "수산물",
    "화학물질",
    "섬유/의류",
    "자동차부품",
]

# 배송 상태
SHIPMENT_STATUSES = [
    "requested",      # 요청됨
    "matched",        # 매칭됨
    "pickup_pending", # 픽업 대기
    "in_transit",     # 운송 중
    "delivered",      # 배송 완료
    "cancelled",      # 취소됨
]

# 한국 이름 생성용 데이터
KOREAN_LAST_NAMES = ["김", "이", "박", "최", "정", "강", "조", "윤", "장", "임"]
KOREAN_FIRST_NAMES = ["민수", "지훈", "서연", "예진", "현우", "수진", "동현", "미영", "준호", "유진"]
COMPANY_SUFFIXES = ["물류", "운송", "로지스틱스", "택배", "화물", "익스프레스", "트랜스포트", "카고"]


# =============================================================================
# 데이터 생성 함수
# =============================================================================

def generate_business_number() -> str:
    """사업자등록번호 생성 (xxx-xx-xxxxx 형식)"""
    return f"{random.randint(100, 999)}-{random.randint(10, 99)}-{random.randint(10000, 99999)}"


def generate_korean_name() -> str:
    """한국어 이름 생성"""
    return random.choice(KOREAN_LAST_NAMES) + random.choice(KOREAN_FIRST_NAMES)


def generate_company_name(prefix: str) -> str:
    """회사명 생성"""
    return f"{prefix}{random.choice(COMPANY_SUFFIXES)}"


def generate_email(name: str, domain: str) -> str:
    """이메일 생성"""
    return f"{name.lower().replace(' ', '.')}@{domain}"


def generate_phone() -> str:
    """전화번호 생성"""
    return f"010-{random.randint(1000, 9999)}-{random.randint(1000, 9999)}"


def generate_license_plate() -> str:
    """차량 번호판 생성 (xx가xxxx 형식)"""
    regions = ["서울", "부산", "인천", "대구", "광주", "대전", "울산", "경기", "강원", "충북", "충남", "전북", "전남", "경북", "경남", "제주"]
    letters = "가나다라마바사아자차카타파하거너더러머버서어저처커터퍼허"
    return f"{random.choice(regions)}{random.choice(letters)}{random.randint(1000, 9999)}"


def generate_datetime_range(days_back: int = 30) -> Tuple[datetime, datetime]:
    """날짜 범위 생성"""
    start = datetime.now() - timedelta(days=random.randint(1, days_back))
    end = start + timedelta(hours=random.randint(4, 72))
    return start, end


# =============================================================================
# OWL 온톨로지 생성 클래스
# =============================================================================

class MiddlemileOntologyGenerator:
    """Middlemile 물류 시스템 OWL 온톨로지 생성기"""

    def __init__(self):
        self.graph = Graph()
        self.graph.bind("mm", MM)
        self.graph.bind("mmi", MMI)
        self.graph.bind("owl", OWL)
        self.graph.bind("rdfs", RDFS)
        self.graph.bind("xsd", XSD)

        # 생성된 인스턴스 추적
        self.shippers: List[URIRef] = []
        self.carriers: List[URIRef] = []
        self.vehicles: List[URIRef] = []
        self.cargos: List[URIRef] = []
        self.locations: List[URIRef] = []
        self.shipments: List[URIRef] = []

    def create_ontology_schema(self):
        """온톨로지 스키마 (TBox) 생성"""
        print("📋 온톨로지 스키마 생성 중...")

        # Ontology 메타데이터
        ontology_uri = URIRef("http://capora.ai/ontology/middlemile")
        self.graph.add((ontology_uri, RDF.type, OWL.Ontology))
        self.graph.add((ontology_uri, RDFS.label, Literal("Middlemile Logistics Ontology", lang="en")))
        self.graph.add((ontology_uri, RDFS.label, Literal("중간마일 물류 온톨로지", lang="ko")))
        self.graph.add((ontology_uri, RDFS.comment, Literal(
            "화주와 운송사 간의 중간마일 물류 서비스를 위한 온톨로지", lang="ko")))
        self.graph.add((ontology_uri, OWL.versionInfo, Literal("1.0.0")))

        # =========================================================================
        # Classes 정의
        # =========================================================================
        classes = [
            (MM.Shipper, "Shipper", "화주", "화물을 보내는 기업 또는 개인"),
            (MM.Carrier, "Carrier", "운송사", "운송 서비스를 제공하는 기업"),
            (MM.Vehicle, "Vehicle", "차량", "화물 운송에 사용되는 차량"),
            (MM.Cargo, "Cargo", "화물", "운송 대상 물품"),
            (MM.Location, "Location", "위치", "물류 관련 장소"),
            (MM.LogisticsCenter, "LogisticsCenter", "물류센터", "화물 집하 및 분류를 위한 시설"),
            (MM.Port, "Port", "항구", "해상 운송을 위한 항만 시설"),
            (MM.Shipment, "Shipment", "배송", "화물 운송 요청 및 진행 건"),
            (MM.MatchingService, "MatchingService", "매칭서비스", "화주와 운송사를 연결하는 서비스"),
            (MM.PricingService, "PricingService", "가격책정서비스", "동적 운송 가격을 책정하는 서비스"),
            (MM.ConsolidationService, "ConsolidationService", "합적서비스", "여러 화물을 합쳐서 운송하는 서비스"),
        ]

        for cls_uri, label_en, label_ko, comment_ko in classes:
            self.graph.add((cls_uri, RDF.type, OWL.Class))
            self.graph.add((cls_uri, RDFS.label, Literal(label_en, lang="en")))
            self.graph.add((cls_uri, RDFS.label, Literal(label_ko, lang="ko")))
            self.graph.add((cls_uri, RDFS.comment, Literal(comment_ko, lang="ko")))

        # 서브클래스 관계
        self.graph.add((MM.LogisticsCenter, RDFS.subClassOf, MM.Location))
        self.graph.add((MM.Port, RDFS.subClassOf, MM.Location))

        # =========================================================================
        # Object Properties 정의
        # =========================================================================
        object_properties = [
            (MM.owns, "owns", "소유", MM.Shipper, MM.Cargo, "화주가 화물을 소유함"),
            (MM.operates, "operates", "운영", MM.Carrier, MM.Vehicle, "운송사가 차량을 운영함"),
            (MM.assignedTo, "assignedTo", "배정됨", MM.Shipment, MM.Vehicle, "배송에 차량이 배정됨"),
            (MM.contains, "contains", "포함", MM.Shipment, MM.Cargo, "배송에 화물이 포함됨"),
            (MM.origin, "origin", "출발지", MM.Shipment, MM.Location, "배송의 출발 위치"),
            (MM.destination, "destination", "목적지", MM.Shipment, MM.Location, "배송의 도착 위치"),
            (MM.requestedBy, "requestedBy", "요청자", MM.Shipment, MM.Shipper, "배송을 요청한 화주"),
            (MM.fulfilledBy, "fulfilledBy", "수행자", MM.Shipment, MM.Carrier, "배송을 수행하는 운송사"),
            (MM.matchesShipper, "matchesShipper", "화주매칭", MM.MatchingService, MM.Shipper, "매칭된 화주"),
            (MM.matchesCarrier, "matchesCarrier", "운송사매칭", MM.MatchingService, MM.Carrier, "매칭된 운송사"),
            (MM.consolidates, "consolidates", "합적화물", MM.ConsolidationService, MM.Cargo, "합적되는 화물"),
            (MM.prices, "prices", "가격책정대상", MM.PricingService, MM.Shipment, "가격이 책정된 배송"),
            (MM.locatedAt, "locatedAt", "위치함", MM.Carrier, MM.Location, "운송사의 위치"),
            (MM.servesRegion, "servesRegion", "서비스지역", MM.Carrier, MM.Location, "운송사가 서비스하는 지역"),
        ]

        for prop_uri, label_en, label_ko, domain, range_, comment_ko in object_properties:
            self.graph.add((prop_uri, RDF.type, OWL.ObjectProperty))
            self.graph.add((prop_uri, RDFS.label, Literal(label_en, lang="en")))
            self.graph.add((prop_uri, RDFS.label, Literal(label_ko, lang="ko")))
            self.graph.add((prop_uri, RDFS.domain, domain))
            self.graph.add((prop_uri, RDFS.range, range_))
            self.graph.add((prop_uri, RDFS.comment, Literal(comment_ko, lang="ko")))

        # =========================================================================
        # Data Properties 정의
        # =========================================================================
        data_properties = [
            # 공통
            (MM.name, "name", "이름", XSD.string),
            (MM.businessNumber, "businessNumber", "사업자등록번호", XSD.string),
            (MM.contactEmail, "contactEmail", "연락이메일", XSD.string),
            (MM.contactPhone, "contactPhone", "연락전화", XSD.string),
            (MM.createdAt, "createdAt", "생성일시", XSD.dateTime),
            (MM.updatedAt, "updatedAt", "수정일시", XSD.dateTime),

            # Vehicle
            (MM.vehicleType, "vehicleType", "차량유형", XSD.string),
            (MM.licensePlate, "licensePlate", "차량번호", XSD.string),
            (MM.capacityKg, "capacityKg", "적재용량(kg)", XSD.decimal),
            (MM.capacityM3, "capacityM3", "적재용량(m3)", XSD.decimal),

            # Cargo
            (MM.cargoType, "cargoType", "화물유형", XSD.string),
            (MM.weightKg, "weightKg", "무게(kg)", XSD.decimal),
            (MM.volumeM3, "volumeM3", "부피(m3)", XSD.decimal),
            (MM.description, "description", "설명", XSD.string),

            # Shipment
            (MM.status, "status", "상태", XSD.string),
            (MM.estimatedPickup, "estimatedPickup", "예상픽업일시", XSD.dateTime),
            (MM.estimatedDelivery, "estimatedDelivery", "예상배송일시", XSD.dateTime),
            (MM.actualPickup, "actualPickup", "실제픽업일시", XSD.dateTime),
            (MM.actualDelivery, "actualDelivery", "실제배송일시", XSD.dateTime),

            # Location
            (MM.address, "address", "주소", XSD.string),
            (MM.latitude, "latitude", "위도", XSD.decimal),
            (MM.longitude, "longitude", "경도", XSD.decimal),
            (MM.locationType, "locationType", "위치유형", XSD.string),

            # Pricing
            (MM.price, "price", "가격", XSD.decimal),
            (MM.currency, "currency", "통화", XSD.string),
            (MM.pricingMethod, "pricingMethod", "가격책정방식", XSD.string),

            # Matching
            (MM.matchedAt, "matchedAt", "매칭일시", XSD.dateTime),
            (MM.matchScore, "matchScore", "매칭점수", XSD.decimal),
        ]

        for prop_uri, label_en, label_ko, datatype in data_properties:
            self.graph.add((prop_uri, RDF.type, OWL.DatatypeProperty))
            self.graph.add((prop_uri, RDFS.label, Literal(label_en, lang="en")))
            self.graph.add((prop_uri, RDFS.label, Literal(label_ko, lang="ko")))
            self.graph.add((prop_uri, RDFS.range, datatype))

        print("   ✅ 클래스 11개, Object Property 14개, Data Property 25개 생성")

    def create_locations(self):
        """물류센터 및 항구 인스턴스 생성"""
        print("📍 위치 데이터 생성 중...")

        # 물류센터 생성
        for lc_id, name, address, lat, lng in LOGISTICS_CENTERS:
            uri = MMI[lc_id]
            self.graph.add((uri, RDF.type, MM.LogisticsCenter))
            self.graph.add((uri, MM.name, Literal(name, lang="ko")))
            self.graph.add((uri, MM.address, Literal(address, lang="ko")))
            self.graph.add((uri, MM.latitude, Literal(lat, datatype=XSD.decimal)))
            self.graph.add((uri, MM.longitude, Literal(lng, datatype=XSD.decimal)))
            self.graph.add((uri, MM.locationType, Literal("logistics_center")))
            self.locations.append(uri)

        # 항구 생성
        for port_id, name, address, lat, lng in PORTS:
            uri = MMI[port_id]
            self.graph.add((uri, RDF.type, MM.Port))
            self.graph.add((uri, MM.name, Literal(name, lang="ko")))
            self.graph.add((uri, MM.address, Literal(address, lang="ko")))
            self.graph.add((uri, MM.latitude, Literal(lat, datatype=XSD.decimal)))
            self.graph.add((uri, MM.longitude, Literal(lng, datatype=XSD.decimal)))
            self.graph.add((uri, MM.locationType, Literal("port")))
            self.locations.append(uri)

        print(f"   ✅ 물류센터 {len(LOGISTICS_CENTERS)}개, 항구 {len(PORTS)}개 생성")

    def create_shippers(self, count: int = 100):
        """화주 인스턴스 생성"""
        print(f"🏭 화주 {count}개 생성 중...")

        company_prefixes = [
            "한진", "삼성", "LG", "현대", "SK", "롯데", "CJ", "대한", "신세계", "이마트",
            "쿠팡", "마켓컬리", "배민", "요기요", "당근", "네이버", "카카오", "토스", "무신사", "오늘의집",
            "GS", "포스코", "한화", "두산", "KT", "농심", "오뚜기", "풀무원", "동원", "빙그레",
        ]

        for i in range(count):
            shipper_id = f"Shipper_{i+1:03d}"
            uri = MMI[shipper_id]

            # 회사명 생성
            if i < len(company_prefixes):
                company_name = f"{company_prefixes[i]} 상사"
            else:
                company_name = f"{generate_korean_name()} 무역 {i+1}"

            self.graph.add((uri, RDF.type, MM.Shipper))
            self.graph.add((uri, MM.name, Literal(company_name, lang="ko")))
            self.graph.add((uri, MM.businessNumber, Literal(generate_business_number())))
            self.graph.add((uri, MM.contactEmail, Literal(generate_email(f"shipper{i+1}", "example.com"))))
            self.graph.add((uri, MM.contactPhone, Literal(generate_phone())))
            self.graph.add((uri, MM.createdAt, Literal(
                (datetime.now() - timedelta(days=random.randint(30, 365))).isoformat(),
                datatype=XSD.dateTime)))

            self.shippers.append(uri)

        print(f"   ✅ 화주 {count}개 생성 완료")

    def create_carriers(self, count: int = 100):
        """운송사 인스턴스 생성 (각 운송사당 1~100대 차량)"""
        print(f"🚚 운송사 {count}개 및 차량 생성 중...")

        total_vehicles = 0

        company_prefixes = [
            "대한통운", "한진택배", "롯데글로벌", "CJ대한통운", "현대", "우체국", "로젠", "경동", "일양", "천일",
            "합동", "건영", "대신", "동부", "세방", "삼성", "범한", "흥아", "유성", "고려",
        ]

        for i in range(count):
            carrier_id = f"Carrier_{i+1:03d}"
            uri = MMI[carrier_id]

            # 회사명 생성
            if i < len(company_prefixes):
                company_name = generate_company_name(company_prefixes[i])
            else:
                company_name = generate_company_name(generate_korean_name())

            self.graph.add((uri, RDF.type, MM.Carrier))
            self.graph.add((uri, MM.name, Literal(company_name, lang="ko")))
            self.graph.add((uri, MM.businessNumber, Literal(generate_business_number())))
            self.graph.add((uri, MM.contactEmail, Literal(generate_email(f"carrier{i+1}", "logistics.co.kr"))))
            self.graph.add((uri, MM.contactPhone, Literal(generate_phone())))
            self.graph.add((uri, MM.createdAt, Literal(
                (datetime.now() - timedelta(days=random.randint(30, 730))).isoformat(),
                datatype=XSD.dateTime)))

            # 운송사 위치 (랜덤 물류센터)
            home_location = random.choice(self.locations)
            self.graph.add((uri, MM.locatedAt, home_location))

            # 서비스 지역 (2~5개 랜덤)
            service_regions = random.sample(self.locations, k=random.randint(2, min(5, len(self.locations))))
            for region in service_regions:
                self.graph.add((uri, MM.servesRegion, region))

            self.carriers.append(uri)

            # 차량 생성 (1~100대)
            vehicle_count = random.randint(1, 100)
            total_vehicles += vehicle_count

            for j in range(vehicle_count):
                vehicle_id = f"Vehicle_{i+1:03d}_{j+1:03d}"
                v_uri = MMI[vehicle_id]

                # 차량 유형 선택
                vtype_id, vtype_name, capacity_kg, capacity_m3 = random.choice(VEHICLE_TYPES)

                self.graph.add((v_uri, RDF.type, MM.Vehicle))
                self.graph.add((v_uri, MM.vehicleType, Literal(vtype_name, lang="ko")))
                self.graph.add((v_uri, MM.licensePlate, Literal(generate_license_plate())))
                self.graph.add((v_uri, MM.capacityKg, Literal(capacity_kg, datatype=XSD.decimal)))
                self.graph.add((v_uri, MM.capacityM3, Literal(capacity_m3, datatype=XSD.decimal)))

                # 운송사 → 차량 관계
                self.graph.add((uri, MM.operates, v_uri))

                self.vehicles.append(v_uri)

        print(f"   ✅ 운송사 {count}개, 차량 총 {total_vehicles}대 생성 완료")

    def create_cargos_and_shipments(self, shipment_count: int = 500):
        """화물 및 배송 인스턴스 생성"""
        print(f"📦 화물 및 배송 {shipment_count}건 생성 중...")

        for i in range(shipment_count):
            # 화물 생성
            cargo_id = f"Cargo_{i+1:04d}"
            c_uri = MMI[cargo_id]

            cargo_type = random.choice(CARGO_TYPES)
            weight = round(random.uniform(100, 10000), 2)
            volume = round(random.uniform(0.5, 30), 2)

            self.graph.add((c_uri, RDF.type, MM.Cargo))
            self.graph.add((c_uri, MM.cargoType, Literal(cargo_type, lang="ko")))
            self.graph.add((c_uri, MM.weightKg, Literal(weight, datatype=XSD.decimal)))
            self.graph.add((c_uri, MM.volumeM3, Literal(volume, datatype=XSD.decimal)))
            self.graph.add((c_uri, MM.description, Literal(f"{cargo_type} 화물 #{i+1}", lang="ko")))

            # 화주 → 화물 소유 관계
            shipper = random.choice(self.shippers)
            self.graph.add((shipper, MM.owns, c_uri))

            self.cargos.append(c_uri)

            # 배송 생성
            shipment_id = f"Shipment_{i+1:04d}"
            s_uri = MMI[shipment_id]

            status = random.choice(SHIPMENT_STATUSES)
            origin = random.choice(self.locations)
            destination = random.choice([loc for loc in self.locations if loc != origin])

            pickup_dt, delivery_dt = generate_datetime_range()

            self.graph.add((s_uri, RDF.type, MM.Shipment))
            self.graph.add((s_uri, MM.status, Literal(status)))
            self.graph.add((s_uri, MM.origin, origin))
            self.graph.add((s_uri, MM.destination, destination))
            self.graph.add((s_uri, MM.contains, c_uri))
            self.graph.add((s_uri, MM.requestedBy, shipper))
            self.graph.add((s_uri, MM.estimatedPickup, Literal(pickup_dt.isoformat(), datatype=XSD.dateTime)))
            self.graph.add((s_uri, MM.estimatedDelivery, Literal(delivery_dt.isoformat(), datatype=XSD.dateTime)))
            self.graph.add((s_uri, MM.createdAt, Literal(
                (pickup_dt - timedelta(hours=random.randint(1, 24))).isoformat(),
                datatype=XSD.dateTime)))

            # 매칭된 경우 운송사와 차량 배정
            if status not in ["requested", "cancelled"]:
                carrier = random.choice(self.carriers)
                self.graph.add((s_uri, MM.fulfilledBy, carrier))

                # 해당 운송사의 차량 찾기
                carrier_vehicles = [v for v in self.vehicles
                                   if (carrier, MM.operates, v) in self.graph]
                if carrier_vehicles:
                    vehicle = random.choice(carrier_vehicles)
                    self.graph.add((s_uri, MM.assignedTo, vehicle))

            # 완료된 경우 실제 시간 추가
            if status == "delivered":
                self.graph.add((s_uri, MM.actualPickup, Literal(pickup_dt.isoformat(), datatype=XSD.dateTime)))
                self.graph.add((s_uri, MM.actualDelivery, Literal(
                    (delivery_dt + timedelta(hours=random.randint(-2, 4))).isoformat(),
                    datatype=XSD.dateTime)))

            self.shipments.append(s_uri)

        print(f"   ✅ 화물 {shipment_count}개, 배송 {shipment_count}건 생성 완료")

    def create_services(self, matching_count: int = 200, consolidation_count: int = 50):
        """매칭, 가격책정, 합적 서비스 인스턴스 생성"""
        print(f"🔄 서비스 인스턴스 생성 중...")

        # 매칭 서비스 생성
        for i in range(matching_count):
            match_id = f"Match_{i+1:04d}"
            m_uri = MMI[match_id]

            shipper = random.choice(self.shippers)
            carrier = random.choice(self.carriers)

            self.graph.add((m_uri, RDF.type, MM.MatchingService))
            self.graph.add((m_uri, MM.matchesShipper, shipper))
            self.graph.add((m_uri, MM.matchesCarrier, carrier))
            self.graph.add((m_uri, MM.matchedAt, Literal(
                (datetime.now() - timedelta(days=random.randint(1, 30))).isoformat(),
                datatype=XSD.dateTime)))
            self.graph.add((m_uri, MM.matchScore, Literal(
                round(random.uniform(0.7, 1.0), 3), datatype=XSD.decimal)))

        # 가격책정 서비스 생성 (배송당)
        pricing_methods = ["distance_based", "weight_based", "volume_based", "dynamic", "fixed"]

        for shipment in self.shipments[:300]:  # 처음 300개 배송에 대해
            price_id = f"Price_{str(shipment).split('#')[1]}"
            p_uri = MMI[price_id]

            self.graph.add((p_uri, RDF.type, MM.PricingService))
            self.graph.add((p_uri, MM.prices, shipment))
            self.graph.add((p_uri, MM.price, Literal(
                round(random.uniform(50000, 500000), 0), datatype=XSD.decimal)))
            self.graph.add((p_uri, MM.currency, Literal("KRW")))
            self.graph.add((p_uri, MM.pricingMethod, Literal(random.choice(pricing_methods))))

        # 합적 서비스 생성
        for i in range(consolidation_count):
            consol_id = f"Consolidation_{i+1:03d}"
            cons_uri = MMI[consol_id]

            self.graph.add((cons_uri, RDF.type, MM.ConsolidationService))

            # 2~5개 화물 합적
            consolidated_cargos = random.sample(self.cargos, k=random.randint(2, 5))
            for cargo in consolidated_cargos:
                self.graph.add((cons_uri, MM.consolidates, cargo))

            self.graph.add((cons_uri, MM.createdAt, Literal(
                (datetime.now() - timedelta(days=random.randint(1, 30))).isoformat(),
                datatype=XSD.dateTime)))

        print(f"   ✅ 매칭서비스 {matching_count}개, 가격책정 300개, 합적서비스 {consolidation_count}개 생성")

    def save(self, output_dir: str = "data"):
        """온톨로지를 파일로 저장"""
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        # OWL/XML 형식
        owl_file = output_path / "middlemile_ontology.owl"
        self.graph.serialize(destination=str(owl_file), format="xml")
        print(f"💾 OWL 파일 저장: {owl_file}")

        # Turtle 형식 (더 읽기 쉬움)
        ttl_file = output_path / "middlemile_ontology.ttl"
        self.graph.serialize(destination=str(ttl_file), format="turtle")
        print(f"💾 Turtle 파일 저장: {ttl_file}")

        # 통계 출력
        print()
        print("📊 생성된 온톨로지 통계:")
        print(f"   - 총 트리플 수: {len(self.graph):,}개")
        print(f"   - 화주 (Shipper): {len(self.shippers)}개")
        print(f"   - 운송사 (Carrier): {len(self.carriers)}개")
        print(f"   - 차량 (Vehicle): {len(self.vehicles)}개")
        print(f"   - 화물 (Cargo): {len(self.cargos)}개")
        print(f"   - 위치 (Location): {len(self.locations)}개")
        print(f"   - 배송 (Shipment): {len(self.shipments)}개")

        return owl_file, ttl_file

    def generate(self, shipper_count: int = 100, carrier_count: int = 100, shipment_count: int = 500):
        """전체 온톨로지 생성"""
        print("=" * 60)
        print("Middlemile 물류 시스템 OWL 온톨로지 생성")
        print("=" * 60)
        print()

        self.create_ontology_schema()
        self.create_locations()
        self.create_shippers(shipper_count)
        self.create_carriers(carrier_count)
        self.create_cargos_and_shipments(shipment_count)
        self.create_services()

        print()
        return self.save()


# =============================================================================
# 메인 실행
# =============================================================================

if __name__ == "__main__":
    import sys

    # 커맨드라인 인자 처리
    shipper_count = 100
    carrier_count = 100
    shipment_count = 500

    if len(sys.argv) > 1:
        shipper_count = int(sys.argv[1])
    if len(sys.argv) > 2:
        carrier_count = int(sys.argv[2])
    if len(sys.argv) > 3:
        shipment_count = int(sys.argv[3])

    generator = MiddlemileOntologyGenerator()
    owl_file, ttl_file = generator.generate(
        shipper_count=shipper_count,
        carrier_count=carrier_count,
        shipment_count=shipment_count
    )

    print()
    print("=" * 60)
    print("✅ 생성 완료!")
    print()
    print("다음 단계:")
    print("1. OWL 파일을 Neo4j에 로드하기 위해 변환 스크립트 실행")
    print("   python -m genai-fundamentals.tools.owl_to_neo4j")
    print()
    print("2. 또는 Protégé 등의 도구로 온톨로지 확인")
    print(f"   - {owl_file}")
    print(f"   - {ttl_file}")
    print("=" * 60)
