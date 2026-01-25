# =============================================================================
# OWL to Neo4j 변환 스크립트
# =============================================================================
# OWL/RDF 온톨로지 파일을 Neo4j 그래프 데이터베이스로 변환하여 로드합니다.
#
# 변환 규칙:
#   - OWL Class Instance → Neo4j Node (라벨 = 클래스명)
#   - OWL Object Property → Neo4j Relationship
#   - OWL Data Property → Neo4j Node Property
#   - rdfs:label → name 속성
#   - URI local name → uri 속성
#
# 지원 포맷:
#   - Turtle (.ttl)
#   - RDF/XML (.owl, .rdf, .xml)
#   - N-Triples (.nt)
#   - N3 (.n3)
#
# 실행 방법:
#   python -m genai-fundamentals.tools.owl_to_neo4j [owl_file] [--clear]
#
# 예시:
#   python -m genai-fundamentals.tools.owl_to_neo4j data/middlemile_ontology.ttl
#   python -m genai-fundamentals.tools.owl_to_neo4j data/middlemile_ontology.owl --clear
# =============================================================================

import argparse
import os
import re
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
from urllib.parse import urlparse

from dotenv import load_dotenv
from neo4j import GraphDatabase
from neo4j.exceptions import AuthError, ServiceUnavailable

try:
    from rdflib import Graph, Namespace, URIRef, Literal, BNode
    from rdflib.namespace import RDF, RDFS, OWL, XSD
except ImportError:
    print("=" * 60)
    print("오류: rdflib 라이브러리가 설치되어 있지 않습니다.")
    print()
    print("설치 방법:")
    print("  pip install rdflib")
    print("=" * 60)
    sys.exit(1)

# .env 파일 로드
load_dotenv()

# =============================================================================
# 상수 정의
# =============================================================================

# Middlemile 온톨로지 네임스페이스
MM = Namespace("http://capora.ai/ontology/middlemile#")
MMI = Namespace("http://capora.ai/ontology/middlemile/instance#")

# Neo4j 연결 정보 (환경변수 또는 기본값)
NEO4J_URI = os.getenv("NEO4J_URI", "neo4j://127.0.0.1:7687")
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "admin123!@#")

# 스키마 클래스 (인스턴스가 아닌 TBox 정의)
SCHEMA_CLASSES = {
    OWL.Class,
    OWL.ObjectProperty,
    OWL.DatatypeProperty,
    OWL.Ontology,
    RDFS.Class,
    RDF.Property,
}

# 무시할 프로퍼티 (메타데이터)
IGNORE_PROPERTIES = {
    RDF.type,
    RDFS.subClassOf,
    RDFS.domain,
    RDFS.range,
    OWL.versionInfo,
}

# XSD 타입 → Python 타입 매핑
XSD_TYPE_MAP = {
    XSD.string: str,
    XSD.integer: int,
    XSD.int: int,
    XSD.long: int,
    XSD.decimal: float,
    XSD.float: float,
    XSD.double: float,
    XSD.boolean: bool,
    XSD.dateTime: str,  # ISO 형식 문자열로 저장
    XSD.date: str,
    XSD.time: str,
}


# =============================================================================
# 데이터 클래스
# =============================================================================

@dataclass
class Neo4jNode:
    """Neo4j 노드 표현"""
    uri: str
    labels: Set[str] = field(default_factory=set)
    properties: Dict[str, Any] = field(default_factory=dict)

    def __hash__(self):
        return hash(self.uri)


@dataclass
class Neo4jRelationship:
    """Neo4j 관계 표현"""
    source_uri: str
    target_uri: str
    rel_type: str
    properties: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ConversionStats:
    """변환 통계"""
    total_triples: int = 0
    nodes_created: int = 0
    relationships_created: int = 0
    properties_set: int = 0
    skipped_schema: int = 0
    skipped_blank: int = 0
    errors: List[str] = field(default_factory=list)


# =============================================================================
# OWL to Neo4j 변환기
# =============================================================================

class OWLToNeo4jConverter:
    """OWL/RDF 온톨로지를 Neo4j로 변환하는 클래스"""

    def __init__(self, neo4j_uri: str, neo4j_user: str, neo4j_password: str):
        self.neo4j_uri = neo4j_uri
        self.neo4j_user = neo4j_user
        self.neo4j_password = neo4j_password
        self.driver = None

        # 변환 결과
        self.nodes: Dict[str, Neo4jNode] = {}
        self.relationships: List[Neo4jRelationship] = []
        self.stats = ConversionStats()

        # RDF 그래프
        self.rdf_graph: Optional[Graph] = None

    def connect(self) -> bool:
        """Neo4j에 연결"""
        try:
            self.driver = GraphDatabase.driver(
                self.neo4j_uri,
                auth=(self.neo4j_user, self.neo4j_password)
            )
            self.driver.verify_connectivity()
            return True
        except ServiceUnavailable:
            print(f"오류: Neo4j 서버에 연결할 수 없습니다 ({self.neo4j_uri})")
            return False
        except AuthError:
            print("오류: Neo4j 인증 실패")
            return False

    def close(self):
        """연결 종료"""
        if self.driver:
            self.driver.close()

    def load_owl(self, file_path: str) -> bool:
        """OWL/RDF 파일 로드"""
        path = Path(file_path)
        if not path.exists():
            print(f"오류: 파일을 찾을 수 없습니다: {file_path}")
            return False

        # 파일 확장자로 포맷 추론
        format_map = {
            '.ttl': 'turtle',
            '.owl': 'xml',
            '.rdf': 'xml',
            '.xml': 'xml',
            '.nt': 'nt',
            '.n3': 'n3',
        }
        file_format = format_map.get(path.suffix.lower(), 'turtle')

        try:
            self.rdf_graph = Graph()
            self.rdf_graph.parse(str(path), format=file_format)
            self.stats.total_triples = len(self.rdf_graph)
            return True
        except Exception as e:
            print(f"오류: 파일 파싱 실패: {e}")
            return False

    def _get_local_name(self, uri: URIRef) -> str:
        """URI에서 로컬 이름 추출"""
        uri_str = str(uri)
        # # 또는 / 뒤의 이름 추출
        if '#' in uri_str:
            return uri_str.split('#')[-1]
        return uri_str.split('/')[-1]

    def _get_class_name(self, uri: URIRef) -> Optional[str]:
        """URI의 클래스명 반환 (인스턴스의 rdf:type)"""
        for _, _, obj in self.rdf_graph.triples((uri, RDF.type, None)):
            if isinstance(obj, URIRef) and obj not in SCHEMA_CLASSES:
                return self._get_local_name(obj)
        return None

    def _is_schema_resource(self, uri: URIRef) -> bool:
        """스키마 리소스인지 확인 (클래스, 프로퍼티 정의 등)"""
        for _, _, obj in self.rdf_graph.triples((uri, RDF.type, None)):
            if obj in SCHEMA_CLASSES:
                return True
        return False

    def _convert_literal(self, literal: Literal) -> Any:
        """RDF Literal을 Python 값으로 변환"""
        if literal.datatype:
            converter = XSD_TYPE_MAP.get(literal.datatype, str)
            try:
                if converter == bool:
                    return str(literal).lower() in ('true', '1', 'yes')
                return converter(str(literal))
            except (ValueError, TypeError):
                return str(literal)
        return str(literal)

    def _sanitize_label(self, name: str) -> str:
        """Neo4j 라벨로 사용 가능하도록 정제"""
        # 특수문자 제거, CamelCase 유지
        sanitized = re.sub(r'[^a-zA-Z0-9_]', '', name)
        if sanitized and sanitized[0].isdigit():
            sanitized = '_' + sanitized
        return sanitized or 'Unknown'

    def _sanitize_rel_type(self, name: str) -> str:
        """Neo4j 관계 타입으로 사용 가능하도록 정제"""
        # 소문자를 대문자로, camelCase를 SNAKE_CASE로
        # 예: assignedTo → ASSIGNED_TO
        s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
        snake = re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).upper()
        return re.sub(r'[^A-Z0-9_]', '', snake) or 'RELATED_TO'

    def _sanitize_property_name(self, name: str) -> str:
        """Neo4j 속성명으로 사용 가능하도록 정제"""
        # camelCase 유지, 특수문자만 제거
        sanitized = re.sub(r'[^a-zA-Z0-9_]', '', name)
        if sanitized and sanitized[0].isdigit():
            sanitized = '_' + sanitized
        return sanitized or 'value'

    def parse_rdf(self):
        """RDF 그래프를 파싱하여 노드와 관계 추출"""
        if not self.rdf_graph:
            return

        print("   트리플 분석 중...")

        # 1단계: 모든 인스턴스 수집
        for subj in self.rdf_graph.subjects(RDF.type, None):
            if isinstance(subj, BNode):
                self.stats.skipped_blank += 1
                continue

            if not isinstance(subj, URIRef):
                continue

            # 스키마 리소스 스킵
            if self._is_schema_resource(subj):
                self.stats.skipped_schema += 1
                continue

            uri_str = str(subj)
            if uri_str not in self.nodes:
                self.nodes[uri_str] = Neo4jNode(uri=uri_str)

            # 클래스명을 라벨로 추가
            class_name = self._get_class_name(subj)
            if class_name:
                self.nodes[uri_str].labels.add(self._sanitize_label(class_name))

            # URI 로컬명 저장
            self.nodes[uri_str].properties['uri'] = self._get_local_name(subj)

        # 2단계: 프로퍼티와 관계 추출
        for subj, pred, obj in self.rdf_graph:
            if isinstance(subj, BNode):
                continue

            subj_str = str(subj)
            if subj_str not in self.nodes:
                continue

            # 무시할 프로퍼티
            if pred in IGNORE_PROPERTIES:
                continue

            pred_name = self._get_local_name(pred)

            # Object Property (URI 타겟) → 관계
            if isinstance(obj, URIRef):
                obj_str = str(obj)
                if obj_str in self.nodes:
                    rel_type = self._sanitize_rel_type(pred_name)
                    self.relationships.append(Neo4jRelationship(
                        source_uri=subj_str,
                        target_uri=obj_str,
                        rel_type=rel_type
                    ))

            # Data Property (Literal) → 노드 속성
            elif isinstance(obj, Literal):
                prop_name = self._sanitize_property_name(pred_name)
                prop_value = self._convert_literal(obj)

                # 언어 태그가 있는 경우 한국어 우선
                if obj.language:
                    existing = self.nodes[subj_str].properties.get(prop_name)
                    if existing is None or obj.language == 'ko':
                        self.nodes[subj_str].properties[prop_name] = prop_value
                else:
                    self.nodes[subj_str].properties[prop_name] = prop_value

        print(f"   - 노드: {len(self.nodes)}개")
        print(f"   - 관계: {len(self.relationships)}개")
        print(f"   - 스킵된 스키마 리소스: {self.stats.skipped_schema}개")
        print(f"   - 스킵된 Blank Node: {self.stats.skipped_blank}개")

    def clear_database(self):
        """기존 데이터 삭제"""
        print("   기존 데이터 삭제 중...")
        with self.driver.session() as session:
            session.run("MATCH (n) DETACH DELETE n")
        print("   - 완료")

    def create_constraints(self):
        """인덱스 및 제약조건 생성"""
        print("   인덱스 생성 중...")
        unique_labels = set()
        for node in self.nodes.values():
            unique_labels.update(node.labels)

        with self.driver.session() as session:
            for label in unique_labels:
                try:
                    # uri 속성에 대한 인덱스 생성
                    session.run(f"""
                        CREATE INDEX IF NOT EXISTS FOR (n:{label}) ON (n.uri)
                    """)
                except Exception as e:
                    # 인덱스 생성 실패는 무시 (이미 존재할 수 있음)
                    pass

        print(f"   - {len(unique_labels)}개 라벨에 대한 인덱스 생성")

    def load_nodes(self):
        """노드 생성"""
        print("   노드 생성 중...")

        with self.driver.session() as session:
            # 배치 처리
            batch_size = 500
            nodes_list = list(self.nodes.values())

            for i in range(0, len(nodes_list), batch_size):
                batch = nodes_list[i:i + batch_size]

                for node in batch:
                    if not node.labels:
                        node.labels.add('Resource')

                    labels_str = ':'.join(node.labels)
                    props = node.properties.copy()

                    # Cypher 쿼리 생성
                    cypher = f"CREATE (n:{labels_str} $props)"

                    try:
                        session.run(cypher, props=props)
                        self.stats.nodes_created += 1
                        self.stats.properties_set += len(props)
                    except Exception as e:
                        self.stats.errors.append(f"노드 생성 실패 ({node.uri}): {e}")

                # 진행률 표시
                progress = min(i + batch_size, len(nodes_list))
                print(f"\r   - {progress}/{len(nodes_list)} 노드 생성", end="")

        print()

    def load_relationships(self):
        """관계 생성"""
        print("   관계 생성 중...")

        with self.driver.session() as session:
            batch_size = 500

            for i in range(0, len(self.relationships), batch_size):
                batch = self.relationships[i:i + batch_size]

                for rel in batch:
                    source_uri = self.nodes[rel.source_uri].properties.get('uri')
                    target_uri = self.nodes[rel.target_uri].properties.get('uri')

                    if not source_uri or not target_uri:
                        continue

                    # 소스와 타겟의 라벨 가져오기
                    source_labels = list(self.nodes[rel.source_uri].labels)
                    target_labels = list(self.nodes[rel.target_uri].labels)

                    if not source_labels or not target_labels:
                        continue

                    # 첫 번째 라벨 사용
                    source_label = source_labels[0]
                    target_label = target_labels[0]

                    cypher = f"""
                        MATCH (a:{source_label} {{uri: $source_uri}})
                        MATCH (b:{target_label} {{uri: $target_uri}})
                        CREATE (a)-[r:{rel.rel_type}]->(b)
                    """

                    try:
                        session.run(cypher, source_uri=source_uri, target_uri=target_uri)
                        self.stats.relationships_created += 1
                    except Exception as e:
                        self.stats.errors.append(
                            f"관계 생성 실패 ({source_uri})-[{rel.rel_type}]->({target_uri}): {e}"
                        )

                # 진행률 표시
                progress = min(i + batch_size, len(self.relationships))
                print(f"\r   - {progress}/{len(self.relationships)} 관계 생성", end="")

        print()

    def print_stats(self):
        """통계 출력"""
        print()
        print("=" * 60)
        print("변환 완료!")
        print("=" * 60)
        print()
        print("통계:")
        print(f"  - 총 트리플 수: {self.stats.total_triples:,}")
        print(f"  - 생성된 노드: {self.stats.nodes_created:,}")
        print(f"  - 생성된 관계: {self.stats.relationships_created:,}")
        print(f"  - 설정된 속성: {self.stats.properties_set:,}")
        print()

        if self.stats.errors:
            print(f"오류 ({len(self.stats.errors)}건):")
            for error in self.stats.errors[:10]:
                print(f"  - {error}")
            if len(self.stats.errors) > 10:
                print(f"  ... 외 {len(self.stats.errors) - 10}건")

    def show_sample_data(self):
        """샘플 데이터 조회"""
        print()
        print("샘플 데이터:")
        print("-" * 60)

        with self.driver.session() as session:
            # 노드 라벨별 개수
            result = session.run("""
                CALL db.labels() YIELD label
                CALL apoc.cypher.run('MATCH (n:`' + label + '`) RETURN count(n) as count', {})
                YIELD value
                RETURN label, value.count as count
                ORDER BY value.count DESC
                LIMIT 15
            """)

            print("노드 라벨별 개수:")
            for record in result:
                print(f"  - {record['label']}: {record['count']:,}개")

            print()

            # 관계 타입별 개수
            result = session.run("""
                CALL db.relationshipTypes() YIELD relationshipType
                CALL apoc.cypher.run(
                    'MATCH ()-[r:`' + relationshipType + '`]->() RETURN count(r) as count', {}
                ) YIELD value
                RETURN relationshipType, value.count as count
                ORDER BY value.count DESC
                LIMIT 15
            """)

            print("관계 타입별 개수:")
            for record in result:
                print(f"  - {record['relationshipType']}: {record['count']:,}개")

    def convert(self, owl_file: str, clear: bool = False) -> bool:
        """전체 변환 프로세스 실행"""
        print("=" * 60)
        print("OWL to Neo4j 변환")
        print("=" * 60)
        print()
        print(f"입력 파일: {owl_file}")
        print(f"Neo4j URI: {self.neo4j_uri}")
        print()

        # 1. OWL 파일 로드
        print("1. OWL 파일 로드 중...")
        if not self.load_owl(owl_file):
            return False
        print(f"   - {self.stats.total_triples:,}개 트리플 로드 완료")
        print()

        # 2. RDF 파싱
        print("2. RDF 데이터 파싱 중...")
        self.parse_rdf()
        print()

        # 3. Neo4j 연결
        print("3. Neo4j 연결 중...")
        if not self.connect():
            return False
        print("   - 연결 성공")
        print()

        try:
            # 4. 기존 데이터 삭제 (옵션)
            if clear:
                print("4. 기존 데이터 삭제...")
                self.clear_database()
                print()

            # 5. 인덱스 생성
            print("5. 인덱스 생성...")
            self.create_constraints()
            print()

            # 6. 노드 생성
            print("6. 노드 생성...")
            self.load_nodes()
            print()

            # 7. 관계 생성
            print("7. 관계 생성...")
            self.load_relationships()

            # 8. 통계 출력
            self.print_stats()

            # 9. 샘플 데이터 조회
            try:
                self.show_sample_data()
            except Exception:
                # APOC이 없는 경우 스킵
                print("(APOC 플러그인 없음 - 샘플 데이터 조회 스킵)")

            return True

        finally:
            self.close()


# =============================================================================
# 메인 실행
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description='OWL/RDF 온톨로지를 Neo4j로 변환',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
예시:
  python -m genai-fundamentals.tools.owl_to_neo4j data/middlemile_ontology.ttl
  python -m genai-fundamentals.tools.owl_to_neo4j data/middlemile_ontology.owl --clear

환경변수:
  NEO4J_URI      - Neo4j 연결 URI (기본: neo4j://127.0.0.1:7687)
  NEO4J_USERNAME - Neo4j 사용자명 (기본: neo4j)
  NEO4J_PASSWORD - Neo4j 비밀번호
        """
    )

    parser.add_argument(
        'owl_file',
        nargs='?',
        default='data/middlemile_ontology.ttl',
        help='OWL/RDF 파일 경로 (기본: data/middlemile_ontology.ttl)'
    )

    parser.add_argument(
        '--clear',
        action='store_true',
        help='변환 전 기존 데이터 삭제'
    )

    parser.add_argument(
        '--uri',
        default=NEO4J_URI,
        help=f'Neo4j URI (기본: {NEO4J_URI})'
    )

    parser.add_argument(
        '--username',
        default=NEO4J_USERNAME,
        help=f'Neo4j 사용자명 (기본: {NEO4J_USERNAME})'
    )

    parser.add_argument(
        '--password',
        default=NEO4J_PASSWORD,
        help='Neo4j 비밀번호'
    )

    args = parser.parse_args()

    converter = OWLToNeo4jConverter(
        neo4j_uri=args.uri,
        neo4j_user=args.username,
        neo4j_password=args.password
    )

    success = converter.convert(args.owl_file, clear=args.clear)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
