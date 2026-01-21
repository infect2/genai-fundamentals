# =============================================================================
# MIME (Measure of Information in Nodes and Edges) Evaluator
# =============================================================================
# Ontology Validator using MIME approach
# 참고 자료: https://medium.com/@aiwithakashgoyal/the-jaguar-problem-the-ontology-nightmare-haunting-your-knowledge-graph-07aed203d256
# 논문: https://arxiv.org/abs/2502.09956
#
# MINE 평가 지표:
#   - Information Retention: 원본 텍스트와 그래프 간 정보 보존율
#   - Ontology Coherence: 온톨로지 스키마 준수 여부
#   - Type Consistency: 엔티티 타입 일관성 (Jaguar Problem 해결)
#
# 실행 방법:
#   python -m genai-fundamentals.mine_evaluator
# =============================================================================

from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
import os
import numpy as np
from dotenv import load_dotenv

load_dotenv()

# -----------------------------------------------------------------------------
# Neo4j 및 OpenAI 연결
# -----------------------------------------------------------------------------
from neo4j import GraphDatabase
from openai import OpenAI

# -----------------------------------------------------------------------------
# 영화 데이터 온톨로지 스키마 정의
# -----------------------------------------------------------------------------
MOVIE_ONTOLOGY_SCHEMA = {
    "node_types": {
        "Movie": {
            "required_properties": ["title"],
            "optional_properties": ["plot", "year", "released", "countries", "languages"],
            "property_types": {
                "title": str,
                "plot": str,
                "year": int,
                "released": str,
                "countries": list,
                "languages": list
            }
        },
        "Actor": {
            "required_properties": ["name"],
            "optional_properties": ["born"],
            "property_types": {
                "name": str,
                "born": int
            }
        },
        "Director": {
            "required_properties": ["name"],
            "optional_properties": ["born"],
            "property_types": {
                "name": str,
                "born": int
            }
        },
        "Genre": {
            "required_properties": ["name"],
            "optional_properties": [],
            "property_types": {
                "name": str
            }
        },
        "User": {
            "required_properties": ["userId"],
            "optional_properties": ["name"],
            "property_types": {
                "userId": str,
                "name": str
            }
        }
    },
    "relationship_types": {
        "ACTED_IN": {
            "source": "Actor",
            "target": "Movie",
            "properties": ["roles"]
        },
        "DIRECTED": {
            "source": "Director",
            "target": "Movie",
            "properties": []
        },
        "IN_GENRE": {
            "source": "Movie",
            "target": "Genre",
            "properties": []
        },
        "RATED": {
            "source": "User",
            "target": "Movie",
            "properties": ["rating"]
        }
    },
    # Jaguar Problem 해결을 위한 타입 제약
    "type_constraints": {
        "Actor": {
            "cannot_be": ["Movie", "Genre"],
            "must_have_relationship": ["ACTED_IN"]
        },
        "Director": {
            "cannot_be": ["Movie", "Genre"],
            "must_have_relationship": ["DIRECTED"]
        },
        "Movie": {
            "cannot_be": ["Actor", "Director", "User"],
            "must_have_relationship": []
        }
    }
}


# -----------------------------------------------------------------------------
# 평가 결과 데이터 클래스
# -----------------------------------------------------------------------------
@dataclass
class MINEResult:
    """MINE 평가 결과"""
    overall_score: float
    semantic_similarity: float
    ontology_coherence: float
    type_consistency: float
    details: Dict[str, Any]


# -----------------------------------------------------------------------------
# MIME Evaluator 클래스
# -----------------------------------------------------------------------------
class MINEEvaluator:
    """
    MINE (Measure of Information in Nodes and Edges) evaluator.

    Knowledge Graph의 품질을 다음 기준으로 평가:
    1. Semantic Similarity (50%): 원본 텍스트와 그래프 재구성 텍스트 간 유사도
    2. Ontology Coherence (30%): 정의된 온톨로지 스키마 준수율
    3. Type Consistency (20%): 엔티티 타입 일관성 (Jaguar Problem 해결)

    Based on arXiv:2502.09956 - KGGen paper
    """

    def __init__(
        self,
        neo4j_uri: str = None,
        neo4j_user: str = None,
        neo4j_password: str = None,
        ontology_schema: Dict[str, Any] = None
    ):
        """
        MINE Evaluator 초기화

        Args:
            neo4j_uri: Neo4j 연결 URI (기본: 환경변수)
            neo4j_user: Neo4j 사용자명 (기본: 환경변수)
            neo4j_password: Neo4j 비밀번호 (기본: 환경변수)
            ontology_schema: 온톨로지 스키마 (기본: MOVIE_ONTOLOGY_SCHEMA)
        """
        # Neo4j 연결 설정
        self.neo4j_uri = neo4j_uri or os.getenv("NEO4J_URI")
        self.neo4j_user = neo4j_user or os.getenv("NEO4J_USERNAME")
        self.neo4j_password = neo4j_password or os.getenv("NEO4J_PASSWORD")

        self.driver = GraphDatabase.driver(
            self.neo4j_uri,
            auth=(self.neo4j_user, self.neo4j_password)
        )

        # OpenAI 클라이언트 초기화
        self.openai_client = OpenAI()

        # 온톨로지 스키마
        self.ontology_schema = ontology_schema or MOVIE_ONTOLOGY_SCHEMA

        # 가중치 설정
        self.weights = {
            "semantic_similarity": 0.5,
            "ontology_coherence": 0.3,
            "type_consistency": 0.2
        }

    def close(self):
        """Neo4j 연결 종료"""
        self.driver.close()

    # -------------------------------------------------------------------------
    # 메인 평가 함수
    # -------------------------------------------------------------------------
    def evaluate(self, source_text: str = None) -> MINEResult:
        """
        Knowledge Graph 전체를 MINE 방식으로 평가

        Args:
            source_text: 원본 텍스트 (없으면 그래프에서 추출)

        Returns:
            MINEResult: 평가 결과
        """
        # 그래프 데이터 추출
        graph_data = self._extract_graph_data()

        # 원본 텍스트가 없으면 그래프에서 재구성
        if source_text is None:
            source_text = self._generate_source_text(graph_data)

        # 1. Semantic Similarity 계산
        semantic_sim, semantic_details = self._calculate_semantic_similarity(
            source_text, graph_data
        )

        # 2. Ontology Coherence 계산
        ontology_score, ontology_details = self._validate_ontology_coherence(
            graph_data
        )

        # 3. Type Consistency 계산
        type_score, type_details = self._check_type_consistency(graph_data)

        # 종합 점수 계산
        overall_score = (
            self.weights["semantic_similarity"] * semantic_sim +
            self.weights["ontology_coherence"] * ontology_score +
            self.weights["type_consistency"] * type_score
        )

        return MINEResult(
            overall_score=round(overall_score, 4),
            semantic_similarity=round(semantic_sim, 4),
            ontology_coherence=round(ontology_score, 4),
            type_consistency=round(type_score, 4),
            details={
                "semantic": semantic_details,
                "ontology": ontology_details,
                "type": type_details,
                "graph_stats": {
                    "nodes": len(graph_data["nodes"]),
                    "relationships": len(graph_data["relationships"])
                }
            }
        )

    # -------------------------------------------------------------------------
    # 그래프 데이터 추출
    # -------------------------------------------------------------------------
    def _extract_graph_data(self) -> Dict[str, Any]:
        """Neo4j에서 그래프 데이터 추출"""
        with self.driver.session() as session:
            # 노드 추출
            nodes_result = session.run("""
                MATCH (n)
                RETURN id(n) as id, labels(n) as labels, properties(n) as props
            """)
            nodes = [
                {
                    "id": record["id"],
                    "labels": record["labels"],
                    "properties": dict(record["props"])
                }
                for record in nodes_result
            ]

            # 관계 추출
            rels_result = session.run("""
                MATCH (a)-[r]->(b)
                RETURN id(a) as source, id(b) as target,
                       type(r) as type, properties(r) as props,
                       labels(a) as source_labels, labels(b) as target_labels
            """)
            relationships = [
                {
                    "source": record["source"],
                    "target": record["target"],
                    "type": record["type"],
                    "properties": dict(record["props"]) if record["props"] else {},
                    "source_labels": record["source_labels"],
                    "target_labels": record["target_labels"]
                }
                for record in rels_result
            ]

        return {"nodes": nodes, "relationships": relationships}

    # -------------------------------------------------------------------------
    # 1. Semantic Similarity 계산
    # -------------------------------------------------------------------------
    def _calculate_semantic_similarity(
        self,
        source_text: str,
        graph_data: Dict[str, Any]
    ) -> Tuple[float, Dict[str, Any]]:
        """
        원본 텍스트와 그래프 재구성 텍스트 간 의미적 유사도 계산

        Args:
            source_text: 원본 텍스트
            graph_data: 그래프 데이터

        Returns:
            (유사도 점수, 상세 정보)
        """
        # 그래프에서 텍스트 재구성
        reconstructed_text = self._reconstruct_text_from_graph(graph_data)

        # OpenAI Embeddings로 벡터화
        source_embedding = self._get_embedding(source_text)
        graph_embedding = self._get_embedding(reconstructed_text)

        # Cosine Similarity 계산
        similarity = self._cosine_similarity(source_embedding, graph_embedding)

        return similarity, {
            "source_length": len(source_text),
            "reconstructed_length": len(reconstructed_text),
            "reconstructed_preview": reconstructed_text[:500] + "..." if len(reconstructed_text) > 500 else reconstructed_text
        }

    def _get_embedding(self, text: str) -> List[float]:
        """OpenAI Embeddings API로 텍스트 벡터화"""
        response = self.openai_client.embeddings.create(
            model="text-embedding-3-small",
            input=text
        )
        return response.data[0].embedding

    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """두 벡터 간 코사인 유사도 계산"""
        vec1 = np.array(vec1)
        vec2 = np.array(vec2)
        return float(np.dot(vec1, vec2) / (np.linalg.norm(vec1) * np.linalg.norm(vec2)))

    def _reconstruct_text_from_graph(self, graph_data: Dict[str, Any]) -> str:
        """
        그래프 데이터를 자연어 텍스트로 재구성

        이 함수가 MINE의 핵심 - 그래프가 원본 정보를 얼마나 보존하는지 평가
        """
        sentences = []

        # 노드별 정보 추출
        nodes_by_id = {node["id"]: node for node in graph_data["nodes"]}

        # 영화 정보 재구성
        for node in graph_data["nodes"]:
            if "Movie" in node["labels"]:
                props = node["properties"]
                title = props.get("title", "Unknown")
                year = props.get("year", "")
                plot = props.get("plot", "")

                movie_text = f"{title}"
                if year:
                    movie_text += f" ({year})"
                if plot:
                    movie_text += f" is a movie about: {plot}"
                sentences.append(movie_text)

        # 관계 정보 재구성
        for rel in graph_data["relationships"]:
            source_node = nodes_by_id.get(rel["source"], {})
            target_node = nodes_by_id.get(rel["target"], {})

            source_name = source_node.get("properties", {}).get("name") or \
                         source_node.get("properties", {}).get("title", "Unknown")
            target_name = target_node.get("properties", {}).get("name") or \
                         target_node.get("properties", {}).get("title", "Unknown")

            rel_type = rel["type"]

            if rel_type == "ACTED_IN":
                roles = rel.get("properties", {}).get("roles", [])
                role_str = f" as {', '.join(roles)}" if roles else ""
                sentences.append(f"{source_name} acted in {target_name}{role_str}.")
            elif rel_type == "DIRECTED":
                sentences.append(f"{source_name} directed {target_name}.")
            elif rel_type == "IN_GENRE":
                sentences.append(f"{source_name} is in the {target_name} genre.")
            elif rel_type == "RATED":
                rating = rel.get("properties", {}).get("rating", "")
                sentences.append(f"{source_name} rated {target_name} {rating} stars.")

        return " ".join(sentences)

    def _generate_source_text(self, graph_data: Dict[str, Any]) -> str:
        """원본 텍스트가 없을 때 그래프에서 참조 텍스트 생성"""
        return self._reconstruct_text_from_graph(graph_data)

    # -------------------------------------------------------------------------
    # 2. Ontology Coherence 검증
    # -------------------------------------------------------------------------
    def _validate_ontology_coherence(
        self,
        graph_data: Dict[str, Any]
    ) -> Tuple[float, Dict[str, Any]]:
        """
        온톨로지 스키마 준수 여부 검증

        검증 항목:
        - 노드 타입이 스키마에 정의되어 있는지
        - 필수 속성이 존재하는지
        - 속성 타입이 올바른지
        - 관계 타입과 방향이 올바른지
        """
        violations = []
        total_checks = 0
        passed_checks = 0

        node_types = self.ontology_schema["node_types"]
        rel_types = self.ontology_schema["relationship_types"]

        # 노드 검증
        for node in graph_data["nodes"]:
            for label in node["labels"]:
                if label in node_types:
                    schema = node_types[label]
                    props = node["properties"]

                    # 필수 속성 검사
                    for req_prop in schema["required_properties"]:
                        total_checks += 1
                        if req_prop in props and props[req_prop]:
                            passed_checks += 1
                        else:
                            violations.append({
                                "type": "missing_required_property",
                                "node_label": label,
                                "property": req_prop,
                                "node_id": node["id"]
                            })

                    # 속성 타입 검사
                    for prop_name, prop_value in props.items():
                        if prop_name in schema.get("property_types", {}):
                            total_checks += 1
                            expected_type = schema["property_types"][prop_name]
                            if isinstance(prop_value, expected_type):
                                passed_checks += 1
                            else:
                                violations.append({
                                    "type": "property_type_mismatch",
                                    "node_label": label,
                                    "property": prop_name,
                                    "expected": str(expected_type),
                                    "actual": str(type(prop_value))
                                })
                else:
                    # 알 수 없는 노드 타입
                    total_checks += 1
                    violations.append({
                        "type": "unknown_node_type",
                        "label": label,
                        "node_id": node["id"]
                    })

        # 관계 검증
        for rel in graph_data["relationships"]:
            rel_type = rel["type"]

            if rel_type in rel_types:
                total_checks += 1
                schema = rel_types[rel_type]

                # 소스/타겟 타입 검사
                source_labels = rel["source_labels"]
                target_labels = rel["target_labels"]

                source_valid = schema["source"] in source_labels
                target_valid = schema["target"] in target_labels

                if source_valid and target_valid:
                    passed_checks += 1
                else:
                    violations.append({
                        "type": "relationship_type_mismatch",
                        "rel_type": rel_type,
                        "expected_source": schema["source"],
                        "expected_target": schema["target"],
                        "actual_source": source_labels,
                        "actual_target": target_labels
                    })
            else:
                total_checks += 1
                violations.append({
                    "type": "unknown_relationship_type",
                    "rel_type": rel_type
                })

        # 점수 계산
        score = passed_checks / total_checks if total_checks > 0 else 1.0

        return score, {
            "total_checks": total_checks,
            "passed_checks": passed_checks,
            "violations_count": len(violations),
            "violations": violations[:10]  # 처음 10개만 반환
        }

    # -------------------------------------------------------------------------
    # 3. Type Consistency 검사 (Jaguar Problem 해결)
    # -------------------------------------------------------------------------
    def _check_type_consistency(
        self,
        graph_data: Dict[str, Any]
    ) -> Tuple[float, Dict[str, Any]]:
        """
        엔티티 타입 일관성 검사 (Jaguar Problem 해결)

        Jaguar Problem: 동음이의어로 인한 타입 혼동
        예: "Jaguar"가 자동차인지 동물인지 잘못 분류되는 문제

        검사 항목:
        - 동일 이름의 엔티티가 다른 타입으로 존재하는지
        - 타입 제약 조건 위반 여부
        - 관계를 통한 타입 추론 일관성
        """
        inconsistencies = []
        total_entities = len(graph_data["nodes"])
        consistent_entities = total_entities

        type_constraints = self.ontology_schema.get("type_constraints", {})

        # 이름별 노드 그룹화
        name_to_nodes: Dict[str, List[Dict]] = {}
        for node in graph_data["nodes"]:
            name = node["properties"].get("name") or node["properties"].get("title")
            if name:
                name_lower = name.lower()
                if name_lower not in name_to_nodes:
                    name_to_nodes[name_lower] = []
                name_to_nodes[name_lower].append(node)

        # 동일 이름 다른 타입 검사
        for name, nodes in name_to_nodes.items():
            if len(nodes) > 1:
                labels_set = set()
                for node in nodes:
                    labels_set.update(node["labels"])

                # 동일 이름에 다른 타입이 있으면 잠재적 Jaguar Problem
                if len(labels_set) > 1:
                    # 타입 제약 조건으로 유효성 검사
                    for label in labels_set:
                        if label in type_constraints:
                            cannot_be = type_constraints[label].get("cannot_be", [])
                            conflicts = labels_set.intersection(set(cannot_be))
                            if conflicts:
                                inconsistencies.append({
                                    "type": "jaguar_problem",
                                    "name": name,
                                    "conflicting_types": list(labels_set),
                                    "constraint_violation": list(conflicts)
                                })
                                consistent_entities -= 1

        # 관계 기반 타입 일관성 검사
        nodes_by_id = {node["id"]: node for node in graph_data["nodes"]}

        for rel in graph_data["relationships"]:
            source_node = nodes_by_id.get(rel["source"], {})
            source_labels = source_node.get("labels", [])

            for label in source_labels:
                if label in type_constraints:
                    must_have = type_constraints[label].get("must_have_relationship", [])

                    # 해당 노드가 필수 관계를 가지는지 확인
                    node_relationships = [
                        r["type"] for r in graph_data["relationships"]
                        if r["source"] == rel["source"]
                    ]

                    for required_rel in must_have:
                        if required_rel not in node_relationships:
                            # 이미 기록된 inconsistency가 아닐 때만 추가
                            existing = [i for i in inconsistencies
                                       if i.get("node_id") == rel["source"] and
                                          i.get("missing_relationship") == required_rel]
                            if not existing:
                                inconsistencies.append({
                                    "type": "missing_required_relationship",
                                    "node_id": rel["source"],
                                    "node_label": label,
                                    "missing_relationship": required_rel
                                })

        # 점수 계산
        score = consistent_entities / total_entities if total_entities > 0 else 1.0

        return score, {
            "total_entities": total_entities,
            "consistent_entities": consistent_entities,
            "inconsistencies_count": len(inconsistencies),
            "inconsistencies": inconsistencies[:10],  # 처음 10개만
            "jaguar_problems_found": len([i for i in inconsistencies if i["type"] == "jaguar_problem"])
        }

    # -------------------------------------------------------------------------
    # 유틸리티 함수
    # -------------------------------------------------------------------------
    def print_report(self, result: MINEResult):
        """평가 결과를 보기 좋게 출력"""
        print("=" * 60)
        print("MINE (Measure of Information in Nodes and Edges) Report")
        print("=" * 60)
        print()
        print(f"Overall Score: {result.overall_score:.2%}")
        print()
        print("Component Scores:")
        print(f"  - Semantic Similarity (50%): {result.semantic_similarity:.2%}")
        print(f"  - Ontology Coherence  (30%): {result.ontology_coherence:.2%}")
        print(f"  - Type Consistency    (20%): {result.type_consistency:.2%}")
        print()
        print("Graph Statistics:")
        print(f"  - Total Nodes: {result.details['graph_stats']['nodes']}")
        print(f"  - Total Relationships: {result.details['graph_stats']['relationships']}")
        print()

        # Ontology 위반 사항
        ontology_details = result.details.get("ontology", {})
        if ontology_details.get("violations_count", 0) > 0:
            print(f"Ontology Violations: {ontology_details['violations_count']}")
            for v in ontology_details.get("violations", [])[:5]:
                print(f"  - {v['type']}: {v}")
            print()

        # Type Consistency 이슈
        type_details = result.details.get("type", {})
        if type_details.get("jaguar_problems_found", 0) > 0:
            print(f"Jaguar Problems Found: {type_details['jaguar_problems_found']}")
            for i in type_details.get("inconsistencies", [])[:5]:
                if i["type"] == "jaguar_problem":
                    print(f"  - '{i['name']}' has conflicting types: {i['conflicting_types']}")
            print()

        print("=" * 60)


# -----------------------------------------------------------------------------
# 메인 실행
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    print("MINE Evaluator 초기화 중...")

    # 로컬 Neo4j 연결 정보 (Docker가 아닌 로컬 실행 시)
    LOCAL_NEO4J_URI = "neo4j://127.0.0.1:7687"
    LOCAL_NEO4J_USER = "neo4j"
    LOCAL_NEO4J_PASSWORD = "admin123!@#"

    evaluator = MINEEvaluator(
        neo4j_uri=LOCAL_NEO4J_URI,
        neo4j_user=LOCAL_NEO4J_USER,
        neo4j_password=LOCAL_NEO4J_PASSWORD
    )

    try:
        print("Knowledge Graph 평가 중...")
        result = evaluator.evaluate()

        evaluator.print_report(result)

    except Exception as e:
        print(f"❌ 오류 발생: {e}")
        import traceback
        traceback.print_exc()
    finally:
        evaluator.close()
