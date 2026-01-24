# =============================================================================
# Local Neo4j 연결 테스트 스크립트
# =============================================================================
# 로컬에 설치된 Neo4j 데이터베이스 연결을 테스트합니다.
#
# 실행 방법:
#   python -m genai-fundamentals.tools.verify_local_neo4j
#
# 로컬 Neo4j 기본 설정:
#   - URI: bolt://localhost:7687
#   - Username: neo4j
#   - Password: (설치 시 설정한 비밀번호)
# =============================================================================

from neo4j import GraphDatabase
from neo4j.exceptions import ServiceUnavailable, AuthError
import sys

# -----------------------------------------------------------------------------
# 로컬 Neo4j 기본 연결 정보
# -----------------------------------------------------------------------------
LOCAL_NEO4J_URI = "neo4j://127.0.0.1:7687"
LOCAL_NEO4J_USERNAME = "neo4j"
LOCAL_NEO4J_PASSWORD = "admin123!@#"


def test_connection(uri: str, username: str, password: str) -> bool:
    """
    Neo4j 데이터베이스 연결을 테스트합니다.

    Args:
        uri: Neo4j 연결 URI (예: bolt://localhost:7687)
        username: Neo4j 사용자명
        password: Neo4j 비밀번호

    Returns:
        bool: 연결 성공 여부
    """
    print(f"🔌 Neo4j 연결 테스트 중...")
    print(f"   URI: {uri}")
    print(f"   Username: {username}")
    print()

    try:
        # 드라이버 생성
        driver = GraphDatabase.driver(uri, auth=(username, password))

        # 연결 확인
        driver.verify_connectivity()
        print("✅ 연결 성공!")

        # 서버 정보 조회
        with driver.session() as session:
            # Neo4j 버전 확인
            result = session.run("CALL dbms.components() YIELD name, versions RETURN name, versions")
            for record in result:
                print(f"   서버: {record['name']}")
                print(f"   버전: {record['versions'][0]}")

            # 데이터베이스 목록 확인
            result = session.run("SHOW DATABASES")
            databases = [record['name'] for record in result]
            print(f"   데이터베이스: {', '.join(databases)}")

            # 노드 수 확인
            result = session.run("MATCH (n) RETURN count(n) as count")
            node_count = result.single()['count']
            print(f"   총 노드 수: {node_count:,}")

            # 관계 수 확인
            result = session.run("MATCH ()-[r]->() RETURN count(r) as count")
            rel_count = result.single()['count']
            print(f"   총 관계 수: {rel_count:,}")

            # 노드 레이블 확인
            result = session.run("CALL db.labels() YIELD label RETURN collect(label) as labels")
            labels = result.single()['labels']
            if labels:
                print(f"   노드 레이블: {', '.join(labels)}")

            # 관계 타입 확인
            result = session.run("CALL db.relationshipTypes() YIELD relationshipType RETURN collect(relationshipType) as types")
            rel_types = result.single()['types']
            if rel_types:
                print(f"   관계 타입: {', '.join(rel_types)}")

        driver.close()
        return True

    except ServiceUnavailable as e:
        print(f"❌ 연결 실패: Neo4j 서버에 연결할 수 없습니다.")
        print(f"   Neo4j가 실행 중인지 확인하세요.")
        print(f"   - macOS: brew services start neo4j")
        print(f"   - Docker: docker run -p 7687:7687 -p 7474:7474 neo4j")
        print(f"   오류: {e}")
        return False

    except AuthError as e:
        print(f"❌ 인증 실패: 사용자명 또는 비밀번호가 올바르지 않습니다.")
        print(f"   스크립트의 LOCAL_NEO4J_PASSWORD 값을 확인하세요.")
        print(f"   오류: {e}")
        return False

    except Exception as e:
        print(f"❌ 오류 발생: {e}")
        return False


def test_sample_query(uri: str, username: str, password: str):
    """
    샘플 Cypher 쿼리를 실행합니다.
    """
    print()
    print("🔍 샘플 쿼리 테스트...")

    try:
        driver = GraphDatabase.driver(uri, auth=(username, password))

        with driver.session() as session:
            # 영화 데이터가 있는지 확인
            result = session.run("""
                MATCH (m:Movie)
                RETURN m.title as title, m.year as year
                LIMIT 5
            """)

            movies = list(result)
            if movies:
                print("   영화 데이터 (상위 5개):")
                for movie in movies:
                    title = movie['title']
                    year = movie['year'] or 'N/A'
                    print(f"   - {title} ({year})")
            else:
                print("   ⚠️ Movie 노드가 없습니다.")
                print("   영화 데이터를 로드해야 할 수 있습니다.")

        driver.close()

    except Exception as e:
        print(f"   ❌ 쿼리 실행 실패: {e}")


if __name__ == "__main__":
    print("=" * 60)
    print("Local Neo4j 연결 테스트")
    print("=" * 60)
    print()

    # 커맨드라인 인자로 비밀번호를 받을 수 있음
    password = LOCAL_NEO4J_PASSWORD
    if len(sys.argv) > 1:
        password = sys.argv[1]
        print(f"ℹ️  커맨드라인에서 비밀번호를 사용합니다.")
        print()

    # 연결 테스트
    success = test_connection(LOCAL_NEO4J_URI, LOCAL_NEO4J_USERNAME, password)

    # 연결 성공 시 샘플 쿼리 실행
    if success:
        test_sample_query(LOCAL_NEO4J_URI, LOCAL_NEO4J_USERNAME, password)

    print()
    print("=" * 60)

    # 종료 코드 반환
    sys.exit(0 if success else 1)
