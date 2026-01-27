# =============================================================================
# TAP! Service OWL 온톨로지 데이터 생성기
# =============================================================================
# Neo4j에 로드하기 위한 OWL 형식의 TAP! 서비스 온톨로지 데이터를 생성합니다.
#
# 온톨로지 스키마:
#   Classes:
#     - Customer (고객): TAP! 서비스 사용자
#     - Vehicle (차량): 호출 대상 차량
#     - Driver (운전자): 차량 운전자
#     - Location (위치): 픽업/도착 위치
#     - CallRequest (호출 요청): 차량 호출 건
#     - Booking (예약): 사전 예약 건
#     - Payment (결제): 결제 정보
#     - Feedback (피드백): 서비스 평가
#
#   Relationships:
#     - REQUESTED_BY: CallRequest → Customer
#     - BOOKED_BY: Booking → Customer
#     - PICKUP_AT: CallRequest/Booking → Location
#     - DROPOFF_AT: CallRequest/Booking → Location
#     - FULFILLED_BY: CallRequest → Vehicle
#     - DRIVEN_BY: CallRequest → Driver
#     - PAID_WITH: CallRequest/Booking → Payment
#     - HAS_FEEDBACK: CallRequest → Feedback
#
# 실행 방법:
#   python -m genai-fundamentals.tools.generate_tap_owl
#   python -m genai-fundamentals.tools.generate_tap_owl [고객수] [호출수] [예약수]
#
# 출력:
#   - data/tap_ontology.owl (OWL 파일)
#   - data/tap_ontology.ttl (Turtle 형식)
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

TAP = Namespace("http://capora.ai/ontology/tap#")
TAPI = Namespace("http://capora.ai/ontology/tap/instance#")

# 한국 이름
KOREAN_LAST_NAMES = ["김", "이", "박", "최", "정", "강", "조", "윤", "장", "임",
                     "한", "오", "서", "신", "권", "황", "안", "송", "류", "홍"]
KOREAN_FIRST_NAMES = ["민수", "지훈", "서연", "예진", "현우", "수진", "동현", "미영",
                      "준호", "유진", "성민", "은지", "태현", "소연", "재혁", "하늘",
                      "도윤", "서준", "하은", "지우", "시우", "예은", "수호", "채원"]

MEMBERSHIP_LEVELS = ["basic", "silver", "gold", "platinum"]
MEMBERSHIP_WEIGHTS = [40, 30, 20, 10]

# 서울/수도권 주요 위치
LOCATIONS = [
    ("LOC_Gangnam", "강남역", "서울특별시 강남구 강남대로 396", 37.4979, 127.0276),
    ("LOC_Jamsil", "잠실역", "서울특별시 송파구 올림픽로 240", 37.5133, 127.1001),
    ("LOC_Hongdae", "홍대입구역", "서울특별시 마포구 양화로 188", 37.5573, 126.9246),
    ("LOC_Yeouido", "여의도역", "서울특별시 영등포구 여의대로", 37.5216, 126.9243),
    ("LOC_Itaewon", "이태원역", "서울특별시 용산구 이태원로", 37.5346, 126.9946),
    ("LOC_Myeongdong", "명동역", "서울특별시 중구 명동길", 37.5609, 126.9860),
    ("LOC_Sinchon", "신촌역", "서울특별시 서대문구 신촌역로", 37.5551, 126.9368),
    ("LOC_Gwanghwamun", "광화문역", "서울특별시 종로구 세종대로", 37.5712, 126.9770),
    ("LOC_Samsung", "삼성역", "서울특별시 강남구 테헤란로", 37.5088, 127.0631),
    ("LOC_Sindorim", "신도림역", "서울특별시 구로구 경인로", 37.5088, 126.8913),
    ("LOC_Gimpo_Airport", "김포공항", "서울특별시 강서구 하늘길 112", 37.5586, 126.7942),
    ("LOC_Incheon_Airport", "인천공항", "인천광역시 중구 공항로 272", 37.4602, 126.4407),
    ("LOC_Seoul_Station", "서울역", "서울특별시 중구 한강대로 405", 37.5547, 126.9706),
    ("LOC_Gangbuk", "강북구청", "서울특별시 강북구 도봉로", 37.6396, 127.0257),
    ("LOC_Suwon", "수원역", "경기도 수원시 팔달구 덕영대로", 37.2664, 127.0000),
    ("LOC_Pangyo", "판교역", "경기도 성남시 분당구 판교역로", 37.3945, 127.1110),
    ("LOC_Bundang", "분당서현역", "경기도 성남시 분당구 분당로", 37.3855, 127.1234),
    ("LOC_Ilsan", "일산 라페스타", "경기도 고양시 일산서구 중앙로", 37.6559, 126.7690),
    ("LOC_Incheon_Bupyeong", "부평역", "인천광역시 부평구 부평대로", 37.4891, 126.7236),
    ("LOC_Hanam", "하남 스타필드", "경기도 하남시 미사대로 750", 37.5455, 127.2232),
]

# 차량 유형
VEHICLE_TYPES = [
    ("standard", "일반", 3800),
    ("premium", "프리미엄", 5500),
    ("van", "밴", 7000),
    ("suv", "SUV", 6000),
    ("economy", "이코노미", 2800),
]

VEHICLE_MODELS = [
    ("현대", "소나타"), ("현대", "그랜저"), ("현대", "아반떼"),
    ("현대", "아이오닉5"), ("현대", "스타리아"),
    ("기아", "K5"), ("기아", "K8"), ("기아", "EV6"), ("기아", "카니발"),
    ("제네시스", "G80"), ("제네시스", "G90"),
    ("테슬라", "모델3"), ("테슬라", "모델Y"),
    ("BMW", "5시리즈"), ("벤츠", "E클래스"),
]

# 호출 상태
CALL_STATUSES = ["pending", "matched", "arriving", "in_progress", "completed", "cancelled"]
CALL_STATUS_WEIGHTS = [5, 5, 5, 10, 65, 10]

# 예약 상태
BOOKING_STATUSES = ["confirmed", "pending_payment", "cancelled", "completed"]
BOOKING_STATUS_WEIGHTS = [15, 5, 10, 70]

# 결제
PAYMENT_METHODS = ["card", "cash", "points", "corporate"]
PAYMENT_METHOD_WEIGHTS = [55, 15, 15, 15]
PAYMENT_STATUSES = ["pending", "completed", "refunded", "failed"]

# 피드백
FEEDBACK_CATEGORIES = ["driver", "vehicle", "app", "service"]
FEEDBACK_COMMENTS = [
    "친절하고 안전하게 운전해주셨습니다",
    "차량이 깨끗했어요",
    "빠르게 도착했습니다",
    "경로가 비효율적이었어요",
    "앱이 느려요",
    "결제가 편리했습니다",
    "기사님이 불친절했어요",
    "차량 냄새가 났어요",
    "아주 만족합니다",
    "ETA가 정확했어요",
    "대기 시간이 길었어요",
    "쾌적한 차량이었습니다",
]


# =============================================================================
# 헬퍼 함수
# =============================================================================

def generate_korean_name() -> str:
    return random.choice(KOREAN_LAST_NAMES) + random.choice(KOREAN_FIRST_NAMES)


def generate_phone() -> str:
    return f"010-{random.randint(1000, 9999)}-{random.randint(1000, 9999)}"


def generate_email(name: str, idx: int) -> str:
    return f"user{idx}@example.com"


def generate_license_plate() -> str:
    regions = ["서울", "경기", "인천"]
    letters = "가나다라마바사아자차카타파하"
    return f"{random.choice(regions)}{random.choice(letters)}{random.randint(1000, 9999)}"


# =============================================================================
# OWL 온톨로지 생성 클래스
# =============================================================================

class TAPOntologyGenerator:
    """TAP! Service OWL 온톨로지 생성기"""

    def __init__(self):
        self.graph = Graph()
        self.graph.bind("tap", TAP)
        self.graph.bind("tapi", TAPI)
        self.graph.bind("owl", OWL)
        self.graph.bind("rdfs", RDFS)
        self.graph.bind("xsd", XSD)

        self.customers: List[URIRef] = []
        self.vehicles: List[URIRef] = []
        self.drivers: List[URIRef] = []
        self.locations: List[URIRef] = []
        self.call_requests: List[URIRef] = []
        self.bookings: List[URIRef] = []
        self.payments: List[URIRef] = []
        self.feedbacks: List[URIRef] = []

    def create_ontology_schema(self):
        """온톨로지 스키마 (TBox) 생성"""
        print("📋 TAP! 온톨로지 스키마 생성 중...")

        ontology_uri = URIRef("http://capora.ai/ontology/tap")
        self.graph.add((ontology_uri, RDF.type, OWL.Ontology))
        self.graph.add((ontology_uri, RDFS.label, Literal("TAP! Service Ontology", lang="en")))
        self.graph.add((ontology_uri, RDFS.label, Literal("TAP! 호출 서비스 온톨로지", lang="ko")))
        self.graph.add((ontology_uri, RDFS.comment, Literal(
            "사용자 호출, 예약, 결제, 피드백을 관리하는 온톨로지", lang="ko")))
        self.graph.add((ontology_uri, OWL.versionInfo, Literal("1.0.0")))

        # Classes
        classes = [
            (TAP.Customer, "Customer", "고객", "TAP! 서비스 사용자"),
            (TAP.Vehicle, "Vehicle", "차량", "호출 대상 차량"),
            (TAP.Driver, "Driver", "운전자", "차량 운전자"),
            (TAP.Location, "Location", "위치", "픽업/도착 위치"),
            (TAP.CallRequest, "CallRequest", "호출요청", "차량 호출 건"),
            (TAP.Booking, "Booking", "예약", "사전 예약 건"),
            (TAP.Payment, "Payment", "결제", "결제 정보"),
            (TAP.Feedback, "Feedback", "피드백", "서비스 평가"),
        ]

        for cls_uri, label_en, label_ko, comment_ko in classes:
            self.graph.add((cls_uri, RDF.type, OWL.Class))
            self.graph.add((cls_uri, RDFS.label, Literal(label_en, lang="en")))
            self.graph.add((cls_uri, RDFS.label, Literal(label_ko, lang="ko")))
            self.graph.add((cls_uri, RDFS.comment, Literal(comment_ko, lang="ko")))

        # Object Properties
        object_properties = [
            (TAP.requestedBy, "requestedBy", "요청고객", TAP.CallRequest, TAP.Customer,
             "호출 요청 고객"),
            (TAP.bookedBy, "bookedBy", "예약고객", TAP.Booking, TAP.Customer,
             "예약 고객"),
            (TAP.pickupAt, "pickupAt", "픽업위치", None, TAP.Location,
             "픽업 위치"),
            (TAP.dropoffAt, "dropoffAt", "도착위치", None, TAP.Location,
             "도착 위치"),
            (TAP.fulfilledBy, "fulfilledBy", "배정차량", TAP.CallRequest, TAP.Vehicle,
             "배정된 차량"),
            (TAP.drivenBy, "drivenBy", "배정운전자", TAP.CallRequest, TAP.Driver,
             "배정된 운전자"),
            (TAP.paidWith, "paidWith", "결제정보", None, TAP.Payment,
             "결제 정보"),
            (TAP.hasFeedback, "hasFeedback", "피드백", TAP.CallRequest, TAP.Feedback,
             "서비스 피드백"),
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
            (TAP.name, "name", "이름", XSD.string),
            (TAP.phone, "phone", "전화번호", XSD.string),
            (TAP.email, "email", "이메일", XSD.string),
            (TAP.rating, "rating", "평점", XSD.decimal),
            (TAP.membershipLevel, "membershipLevel", "멤버십등급", XSD.string),
            (TAP.customerId, "customerId", "고객ID", XSD.string),
            (TAP.vehicleType, "vehicleType", "차량유형", XSD.string),
            (TAP.licensePlate, "licensePlate", "차량번호", XSD.string),
            (TAP.brand, "brand", "브랜드", XSD.string),
            (TAP.model, "model", "모델", XSD.string),
            (TAP.baseFare, "baseFare", "기본요금", XSD.decimal),
            (TAP.driverId, "driverId", "운전자ID", XSD.string),
            (TAP.status, "status", "상태", XSD.string),
            (TAP.address, "address", "주소", XSD.string),
            (TAP.latitude, "latitude", "위도", XSD.decimal),
            (TAP.longitude, "longitude", "경도", XSD.decimal),
            (TAP.placeName, "placeName", "장소명", XSD.string),
            (TAP.requestId, "requestId", "요청ID", XSD.string),
            (TAP.requestTime, "requestTime", "요청시간", XSD.dateTime),
            (TAP.eta, "eta", "예상도착시간", XSD.integer),
            (TAP.bookingId, "bookingId", "예약ID", XSD.string),
            (TAP.scheduledTime, "scheduledTime", "예약시간", XSD.dateTime),
            (TAP.paymentId, "paymentId", "결제ID", XSD.string),
            (TAP.amount, "amount", "금액", XSD.decimal),
            (TAP.method, "method", "결제방법", XSD.string),
            (TAP.paidAt, "paidAt", "결제시간", XSD.dateTime),
            (TAP.feedbackId, "feedbackId", "피드백ID", XSD.string),
            (TAP.comment, "comment", "코멘트", XSD.string),
            (TAP.category, "category", "카테고리", XSD.string),
            (TAP.createdAt, "createdAt", "생성일시", XSD.dateTime),
        ]

        for prop_uri, label_en, label_ko, datatype in data_properties:
            self.graph.add((prop_uri, RDF.type, OWL.DatatypeProperty))
            self.graph.add((prop_uri, RDFS.label, Literal(label_en, lang="en")))
            self.graph.add((prop_uri, RDFS.label, Literal(label_ko, lang="ko")))
            self.graph.add((prop_uri, RDFS.range, datatype))

        print(f"   클래스 8개, Object Property 8개, Data Property {len(data_properties)}개 생성")

    def create_locations(self):
        """위치 인스턴스 생성"""
        print(f"📍 위치 {len(LOCATIONS)}개 생성 중...")

        for loc_id, place_name, address, lat, lng in LOCATIONS:
            uri = TAPI[loc_id]
            self.graph.add((uri, RDF.type, TAP.Location))
            self.graph.add((uri, TAP.placeName, Literal(place_name, lang="ko")))
            self.graph.add((uri, TAP.address, Literal(address, lang="ko")))
            self.graph.add((uri, TAP.latitude, Literal(lat, datatype=XSD.decimal)))
            self.graph.add((uri, TAP.longitude, Literal(lng, datatype=XSD.decimal)))
            self.locations.append(uri)

        print(f"   위치 {len(LOCATIONS)}개 생성 완료")

    def create_customers(self, count: int = 200):
        """고객 인스턴스 생성"""
        print(f"👤 고객 {count}명 생성 중...")

        for i in range(count):
            cid = f"CUST_{i+1:04d}"
            uri = TAPI[cid]

            name = generate_korean_name()
            membership = random.choices(MEMBERSHIP_LEVELS, weights=MEMBERSHIP_WEIGHTS, k=1)[0]
            rating = round(random.uniform(3.0, 5.0), 1)

            self.graph.add((uri, RDF.type, TAP.Customer))
            self.graph.add((uri, TAP.customerId, Literal(cid)))
            self.graph.add((uri, TAP.name, Literal(name, lang="ko")))
            self.graph.add((uri, TAP.phone, Literal(generate_phone())))
            self.graph.add((uri, TAP.email, Literal(generate_email(name, i + 1))))
            self.graph.add((uri, TAP.rating, Literal(rating, datatype=XSD.decimal)))
            self.graph.add((uri, TAP.membershipLevel, Literal(membership)))

            self.customers.append(uri)

        print(f"   고객 {count}명 생성 완료")

    def create_vehicles_and_drivers(self, count: int = 80):
        """차량 및 운전자 생성"""
        print(f"🚗 차량/운전자 {count}명 생성 중...")

        for i in range(count):
            # 차량
            vid = f"TAP_V_{i+1:04d}"
            v_uri = TAPI[vid]

            vtype_id, vtype_name, base_fare = random.choice(VEHICLE_TYPES)
            brand, model = random.choice(VEHICLE_MODELS)

            self.graph.add((v_uri, RDF.type, TAP.Vehicle))
            self.graph.add((v_uri, TAP.vehicleType, Literal(vtype_id)))
            self.graph.add((v_uri, TAP.licensePlate, Literal(generate_license_plate())))
            self.graph.add((v_uri, TAP.brand, Literal(brand, lang="ko")))
            self.graph.add((v_uri, TAP.model, Literal(model, lang="ko")))
            self.graph.add((v_uri, TAP.baseFare, Literal(base_fare, datatype=XSD.decimal)))

            self.vehicles.append(v_uri)

            # 운전자
            did = f"TAP_D_{i+1:04d}"
            d_uri = TAPI[did]

            name = generate_korean_name()
            rating = round(random.uniform(3.5, 5.0), 1)

            self.graph.add((d_uri, RDF.type, TAP.Driver))
            self.graph.add((d_uri, TAP.driverId, Literal(did)))
            self.graph.add((d_uri, TAP.name, Literal(name, lang="ko")))
            self.graph.add((d_uri, TAP.phone, Literal(generate_phone())))
            self.graph.add((d_uri, TAP.rating, Literal(rating, datatype=XSD.decimal)))
            self.graph.add((d_uri, TAP.status, Literal("active")))

            self.drivers.append(d_uri)

        print(f"   차량 {count}대, 운전자 {count}명 생성 완료")

    def create_call_requests(self, count: int = 500):
        """호출 요청 생성"""
        print(f"📱 호출 요청 {count}건 생성 중...")

        payment_idx = 0
        feedback_idx = 0

        for i in range(count):
            rid = f"CALL_{i+1:05d}"
            uri = TAPI[rid]

            status = random.choices(CALL_STATUSES, weights=CALL_STATUS_WEIGHTS, k=1)[0]
            req_time = datetime.now() - timedelta(
                days=random.randint(0, 60),
                hours=random.randint(0, 23),
                minutes=random.randint(0, 59)
            )
            eta = random.randint(3, 25)  # 분
            customer = random.choice(self.customers)
            pickup = random.choice(self.locations)
            dropoff = random.choice([l for l in self.locations if l != pickup])

            self.graph.add((uri, RDF.type, TAP.CallRequest))
            self.graph.add((uri, TAP.requestId, Literal(rid)))
            self.graph.add((uri, TAP.status, Literal(status)))
            self.graph.add((uri, TAP.requestTime, Literal(
                req_time.isoformat(), datatype=XSD.dateTime)))
            self.graph.add((uri, TAP.eta, Literal(eta, datatype=XSD.integer)))

            # Relationships
            self.graph.add((uri, TAP.requestedBy, customer))
            self.graph.add((uri, TAP.pickupAt, pickup))
            self.graph.add((uri, TAP.dropoffAt, dropoff))

            # 매칭 이후 상태: 차량/운전자 배정
            if status not in ("pending", "cancelled"):
                idx = random.randint(0, len(self.vehicles) - 1)
                self.graph.add((uri, TAP.fulfilledBy, self.vehicles[idx]))
                self.graph.add((uri, TAP.drivenBy, self.drivers[idx]))

            # 완료 건: 결제 생성
            if status == "completed":
                payment_idx += 1
                pid = f"PAY_{payment_idx:05d}"
                p_uri = TAPI[pid]

                method = random.choices(PAYMENT_METHODS, weights=PAYMENT_METHOD_WEIGHTS, k=1)[0]
                amount = random.randint(5000, 80000)
                paid_at = req_time + timedelta(minutes=random.randint(10, 60))

                self.graph.add((p_uri, RDF.type, TAP.Payment))
                self.graph.add((p_uri, TAP.paymentId, Literal(pid)))
                self.graph.add((p_uri, TAP.amount, Literal(amount, datatype=XSD.decimal)))
                self.graph.add((p_uri, TAP.method, Literal(method)))
                self.graph.add((p_uri, TAP.status, Literal("completed")))
                self.graph.add((p_uri, TAP.paidAt, Literal(
                    paid_at.isoformat(), datatype=XSD.dateTime)))

                self.graph.add((uri, TAP.paidWith, p_uri))
                self.payments.append(p_uri)

                # 피드백 (완료 건의 60%)
                if random.random() < 0.6:
                    feedback_idx += 1
                    fid = f"FB_{feedback_idx:05d}"
                    f_uri = TAPI[fid]

                    fb_rating = random.choices(
                        [1, 2, 3, 4, 5], weights=[3, 5, 10, 30, 52], k=1
                    )[0]
                    category = random.choice(FEEDBACK_CATEGORIES)
                    comment = random.choice(FEEDBACK_COMMENTS)

                    self.graph.add((f_uri, RDF.type, TAP.Feedback))
                    self.graph.add((f_uri, TAP.feedbackId, Literal(fid)))
                    self.graph.add((f_uri, TAP.rating, Literal(fb_rating, datatype=XSD.decimal)))
                    self.graph.add((f_uri, TAP.category, Literal(category)))
                    self.graph.add((f_uri, TAP.comment, Literal(comment, lang="ko")))
                    self.graph.add((f_uri, TAP.createdAt, Literal(
                        (paid_at + timedelta(minutes=random.randint(5, 120))).isoformat(),
                        datatype=XSD.dateTime)))

                    self.graph.add((uri, TAP.hasFeedback, f_uri))
                    self.feedbacks.append(f_uri)

            self.call_requests.append(uri)

        print(f"   호출 {count}건, 결제 {payment_idx}건, 피드백 {feedback_idx}건 생성 완료")

    def create_bookings(self, count: int = 100):
        """예약 생성"""
        print(f"📅 예약 {count}건 생성 중...")

        booking_payment_idx = len(self.payments)

        for i in range(count):
            bid = f"BK_{i+1:04d}"
            uri = TAPI[bid]

            status = random.choices(BOOKING_STATUSES, weights=BOOKING_STATUS_WEIGHTS, k=1)[0]
            scheduled = datetime.now() + timedelta(
                days=random.randint(-30, 14),
                hours=random.randint(6, 22)
            )
            customer = random.choice(self.customers)
            pickup = random.choice(self.locations)
            dropoff = random.choice([l for l in self.locations if l != pickup])

            self.graph.add((uri, RDF.type, TAP.Booking))
            self.graph.add((uri, TAP.bookingId, Literal(bid)))
            self.graph.add((uri, TAP.status, Literal(status)))
            self.graph.add((uri, TAP.scheduledTime, Literal(
                scheduled.isoformat(), datatype=XSD.dateTime)))

            self.graph.add((uri, TAP.bookedBy, customer))
            self.graph.add((uri, TAP.pickupAt, pickup))
            self.graph.add((uri, TAP.dropoffAt, dropoff))

            # 완료 건: 결제
            if status == "completed":
                booking_payment_idx += 1
                pid = f"PAY_{booking_payment_idx:05d}"
                p_uri = TAPI[pid]

                method = random.choices(PAYMENT_METHODS, weights=PAYMENT_METHOD_WEIGHTS, k=1)[0]
                amount = random.randint(5000, 80000)

                self.graph.add((p_uri, RDF.type, TAP.Payment))
                self.graph.add((p_uri, TAP.paymentId, Literal(pid)))
                self.graph.add((p_uri, TAP.amount, Literal(amount, datatype=XSD.decimal)))
                self.graph.add((p_uri, TAP.method, Literal(method)))
                self.graph.add((p_uri, TAP.status, Literal("completed")))
                self.graph.add((p_uri, TAP.paidAt, Literal(
                    (scheduled + timedelta(minutes=random.randint(15, 60))).isoformat(),
                    datatype=XSD.dateTime)))

                self.graph.add((uri, TAP.paidWith, p_uri))
                self.payments.append(p_uri)

            self.bookings.append(uri)

        print(f"   예약 {count}건 생성 완료 (총 결제 {len(self.payments)}건)")

    def save(self, output_dir: str = "data"):
        """온톨로지를 파일로 저장"""
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        owl_file = output_path / "tap_ontology.owl"
        self.graph.serialize(destination=str(owl_file), format="xml")
        print(f"💾 OWL 파일 저장: {owl_file}")

        ttl_file = output_path / "tap_ontology.ttl"
        self.graph.serialize(destination=str(ttl_file), format="turtle")
        print(f"💾 Turtle 파일 저장: {ttl_file}")

        print()
        print("📊 생성된 온톨로지 통계:")
        print(f"   - 총 트리플 수: {len(self.graph):,}개")
        print(f"   - 고객 (Customer): {len(self.customers)}명")
        print(f"   - 차량 (Vehicle): {len(self.vehicles)}대")
        print(f"   - 운전자 (Driver): {len(self.drivers)}명")
        print(f"   - 위치 (Location): {len(self.locations)}개")
        print(f"   - 호출요청 (CallRequest): {len(self.call_requests)}건")
        print(f"   - 예약 (Booking): {len(self.bookings)}건")
        print(f"   - 결제 (Payment): {len(self.payments)}건")
        print(f"   - 피드백 (Feedback): {len(self.feedbacks)}건")

        return owl_file, ttl_file

    def generate(self, customer_count: int = 200, call_count: int = 500,
                 booking_count: int = 100):
        """전체 온톨로지 생성"""
        print("=" * 60)
        print("TAP! Service OWL 온톨로지 생성")
        print("=" * 60)
        print()

        self.create_ontology_schema()
        self.create_locations()
        self.create_customers(customer_count)
        self.create_vehicles_and_drivers(80)
        self.create_call_requests(call_count)
        self.create_bookings(booking_count)

        print()
        return self.save()


# =============================================================================
# 메인 실행
# =============================================================================

if __name__ == "__main__":
    import sys

    customer_count = 200
    call_count = 500
    booking_count = 100

    if len(sys.argv) > 1:
        customer_count = int(sys.argv[1])
    if len(sys.argv) > 2:
        call_count = int(sys.argv[2])
    if len(sys.argv) > 3:
        booking_count = int(sys.argv[3])

    generator = TAPOntologyGenerator()
    owl_file, ttl_file = generator.generate(
        customer_count=customer_count,
        call_count=call_count,
        booking_count=booking_count
    )

    print()
    print("=" * 60)
    print("생성 완료!")
    print()
    print("다음 단계:")
    print("1. Neo4j에 로드:")
    print("   python -m genai-fundamentals.tools.owl_to_neo4j data/tap_ontology.ttl --clear")
    print()
    print("2. 온톨로지 확인:")
    print(f"   - {owl_file}")
    print(f"   - {ttl_file}")
    print("=" * 60)
