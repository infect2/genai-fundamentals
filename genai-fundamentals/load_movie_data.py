# =============================================================================
# Neo4j 영화 데이터 로드 스크립트
# =============================================================================
# GraphRAG 테스트를 위한 샘플 영화 데이터를 Neo4j에 로드합니다.
#
# 데이터 스키마:
#   - Movie (title, plot, year, released, countries, languages)
#   - Actor (name, born)
#   - Director (name, born)
#   - Genre (name)
#   - User (name, userId)
#
# 관계:
#   - (Actor)-[:ACTED_IN]->(Movie)
#   - (Director)-[:DIRECTED]->(Movie)
#   - (Movie)-[:IN_GENRE]->(Genre)
#   - (User)-[:RATED {rating: float}]->(Movie)
#
# 실행 방법:
#   python -m genai-fundamentals.load_movie_data
# =============================================================================

from neo4j import GraphDatabase
from neo4j.exceptions import ServiceUnavailable, AuthError
import sys

# -----------------------------------------------------------------------------
# 로컬 Neo4j 연결 정보
# -----------------------------------------------------------------------------
LOCAL_NEO4J_URI = "neo4j://127.0.0.1:7687"
LOCAL_NEO4J_USERNAME = "neo4j"
LOCAL_NEO4J_PASSWORD = "admin123!@#"

# -----------------------------------------------------------------------------
# 영화 데이터 (Neo4j 공식 샘플 + 확장)
# -----------------------------------------------------------------------------
MOVIE_DATA = """
// 기존 데이터 삭제 (선택사항)
MATCH (n) DETACH DELETE n;

// ============================================================================
// 장르 생성
// ============================================================================
CREATE (action:Genre {name: 'Action'})
CREATE (scifi:Genre {name: 'Sci-Fi'})
CREATE (drama:Genre {name: 'Drama'})
CREATE (thriller:Genre {name: 'Thriller'})
CREATE (crime:Genre {name: 'Crime'})
CREATE (romance:Genre {name: 'Romance'})
CREATE (comedy:Genre {name: 'Comedy'})

// ============================================================================
// 영화 및 관계 생성
// ============================================================================

// The Matrix (1999)
CREATE (matrix:Movie {
  title: 'Matrix, The',
  plot: 'A computer hacker learns from mysterious rebels about the true nature of his reality and his role in the war against its controllers.',
  year: 1999,
  released: '1999-03-31',
  countries: ['USA'],
  languages: ['English']
})
CREATE (keanu:Actor {name: 'Keanu Reeves', born: 1964})
CREATE (laurence:Actor {name: 'Laurence Fishburne', born: 1961})
CREATE (carrieanne:Actor {name: 'Carrie-Anne Moss', born: 1967})
CREATE (hugo:Actor {name: 'Hugo Weaving', born: 1960})
CREATE (wachowskis:Director {name: 'Lana Wachowski', born: 1965})
CREATE (keanu)-[:ACTED_IN {roles: ['Neo']}]->(matrix)
CREATE (laurence)-[:ACTED_IN {roles: ['Morpheus']}]->(matrix)
CREATE (carrieanne)-[:ACTED_IN {roles: ['Trinity']}]->(matrix)
CREATE (hugo)-[:ACTED_IN {roles: ['Agent Smith']}]->(matrix)
CREATE (wachowskis)-[:DIRECTED]->(matrix)
CREATE (matrix)-[:IN_GENRE]->(action)
CREATE (matrix)-[:IN_GENRE]->(scifi)

// The Godfather (1972)
CREATE (godfather:Movie {
  title: 'Godfather, The',
  plot: 'The aging patriarch of an organized crime dynasty transfers control of his clandestine empire to his reluctant son.',
  year: 1972,
  released: '1972-03-24',
  countries: ['USA'],
  languages: ['English', 'Italian']
})
CREATE (marlon:Actor {name: 'Marlon Brando', born: 1924})
CREATE (alpacino:Actor {name: 'Al Pacino', born: 1940})
CREATE (jamescaan:Actor {name: 'James Caan', born: 1940})
CREATE (coppola:Director {name: 'Francis Ford Coppola', born: 1939})
CREATE (marlon)-[:ACTED_IN {roles: ['Don Vito Corleone']}]->(godfather)
CREATE (alpacino)-[:ACTED_IN {roles: ['Michael Corleone']}]->(godfather)
CREATE (jamescaan)-[:ACTED_IN {roles: ['Sonny Corleone']}]->(godfather)
CREATE (coppola)-[:DIRECTED]->(godfather)
CREATE (godfather)-[:IN_GENRE]->(crime)
CREATE (godfather)-[:IN_GENRE]->(drama)

// Inception (2010)
CREATE (inception:Movie {
  title: 'Inception',
  plot: 'A thief who steals corporate secrets through the use of dream-sharing technology is given the inverse task of planting an idea into the mind of a C.E.O.',
  year: 2010,
  released: '2010-07-16',
  countries: ['USA', 'UK'],
  languages: ['English', 'Japanese', 'French']
})
CREATE (leo:Actor {name: 'Leonardo DiCaprio', born: 1974})
CREATE (tom:Actor {name: 'Tom Hardy', born: 1977})
CREATE (ellen:Actor {name: 'Elliot Page', born: 1987})
CREATE (nolan:Director {name: 'Christopher Nolan', born: 1970})
CREATE (leo)-[:ACTED_IN {roles: ['Cobb']}]->(inception)
CREATE (tom)-[:ACTED_IN {roles: ['Eames']}]->(inception)
CREATE (ellen)-[:ACTED_IN {roles: ['Ariadne']}]->(inception)
CREATE (nolan)-[:DIRECTED]->(inception)
CREATE (inception)-[:IN_GENRE]->(scifi)
CREATE (inception)-[:IN_GENRE]->(action)
CREATE (inception)-[:IN_GENRE]->(thriller)

// Forrest Gump (1994)
CREATE (forrest:Movie {
  title: 'Forrest Gump',
  plot: 'The presidencies of Kennedy and Johnson, the Vietnam War, the Watergate scandal and other historical events unfold from the perspective of an Alabama man with an IQ of 75.',
  year: 1994,
  released: '1994-07-06',
  countries: ['USA'],
  languages: ['English']
})
CREATE (tomhanks:Actor {name: 'Tom Hanks', born: 1956})
CREATE (robinwright:Actor {name: 'Robin Wright', born: 1966})
CREATE (garysinise:Actor {name: 'Gary Sinise', born: 1955})
CREATE (zemeckis:Director {name: 'Robert Zemeckis', born: 1952})
CREATE (tomhanks)-[:ACTED_IN {roles: ['Forrest Gump']}]->(forrest)
CREATE (robinwright)-[:ACTED_IN {roles: ['Jenny Curran']}]->(forrest)
CREATE (garysinise)-[:ACTED_IN {roles: ['Lt. Dan Taylor']}]->(forrest)
CREATE (zemeckis)-[:DIRECTED]->(forrest)
CREATE (forrest)-[:IN_GENRE]->(drama)
CREATE (forrest)-[:IN_GENRE]->(romance)

// Pulp Fiction (1994)
CREATE (pulp:Movie {
  title: 'Pulp Fiction',
  plot: 'The lives of two mob hitmen, a boxer, a gangster and his wife, and a pair of diner bandits intertwine in four tales of violence and redemption.',
  year: 1994,
  released: '1994-10-14',
  countries: ['USA'],
  languages: ['English', 'Spanish', 'French']
})
CREATE (johntravolta:Actor {name: 'John Travolta', born: 1954})
CREATE (samuel:Actor {name: 'Samuel L. Jackson', born: 1948})
CREATE (uma:Actor {name: 'Uma Thurman', born: 1970})
CREATE (tarantino:Director {name: 'Quentin Tarantino', born: 1963})
CREATE (johntravolta)-[:ACTED_IN {roles: ['Vincent Vega']}]->(pulp)
CREATE (samuel)-[:ACTED_IN {roles: ['Jules Winnfield']}]->(pulp)
CREATE (uma)-[:ACTED_IN {roles: ['Mia Wallace']}]->(pulp)
CREATE (tarantino)-[:DIRECTED]->(pulp)
CREATE (pulp)-[:IN_GENRE]->(crime)
CREATE (pulp)-[:IN_GENRE]->(thriller)

// The Dark Knight (2008)
CREATE (darkknight:Movie {
  title: 'Dark Knight, The',
  plot: 'When the menace known as the Joker wreaks havoc and chaos on the people of Gotham, Batman must accept one of the greatest psychological and physical tests of his ability to fight injustice.',
  year: 2008,
  released: '2008-07-18',
  countries: ['USA', 'UK'],
  languages: ['English', 'Mandarin']
})
CREATE (christian:Actor {name: 'Christian Bale', born: 1974})
CREATE (heath:Actor {name: 'Heath Ledger', born: 1979})
CREATE (aaron:Actor {name: 'Aaron Eckhart', born: 1968})
CREATE (christian)-[:ACTED_IN {roles: ['Bruce Wayne']}]->(darkknight)
CREATE (heath)-[:ACTED_IN {roles: ['Joker']}]->(darkknight)
CREATE (aaron)-[:ACTED_IN {roles: ['Harvey Dent']}]->(darkknight)
CREATE (nolan)-[:DIRECTED]->(darkknight)
CREATE (darkknight)-[:IN_GENRE]->(action)
CREATE (darkknight)-[:IN_GENRE]->(crime)
CREATE (darkknight)-[:IN_GENRE]->(thriller)

// Titanic (1997)
CREATE (titanic:Movie {
  title: 'Titanic',
  plot: 'A seventeen-year-old aristocrat falls in love with a kind but poor artist aboard the luxurious, ill-fated R.M.S. Titanic.',
  year: 1997,
  released: '1997-12-19',
  countries: ['USA'],
  languages: ['English', 'Swedish', 'Italian']
})
CREATE (kate:Actor {name: 'Kate Winslet', born: 1975})
CREATE (cameron:Director {name: 'James Cameron', born: 1954})
CREATE (leo)-[:ACTED_IN {roles: ['Jack Dawson']}]->(titanic)
CREATE (kate)-[:ACTED_IN {roles: ['Rose DeWitt Bukater']}]->(titanic)
CREATE (cameron)-[:DIRECTED]->(titanic)
CREATE (titanic)-[:IN_GENRE]->(drama)
CREATE (titanic)-[:IN_GENRE]->(romance)

// Interstellar (2014)
CREATE (interstellar:Movie {
  title: 'Interstellar',
  plot: 'A team of explorers travel through a wormhole in space in an attempt to ensure humanitys survival.',
  year: 2014,
  released: '2014-11-07',
  countries: ['USA', 'UK', 'Canada'],
  languages: ['English']
})
CREATE (matthew:Actor {name: 'Matthew McConaughey', born: 1969})
CREATE (anne:Actor {name: 'Anne Hathaway', born: 1982})
CREATE (jessica:Actor {name: 'Jessica Chastain', born: 1977})
CREATE (matthew)-[:ACTED_IN {roles: ['Cooper']}]->(interstellar)
CREATE (anne)-[:ACTED_IN {roles: ['Brand']}]->(interstellar)
CREATE (jessica)-[:ACTED_IN {roles: ['Murph']}]->(interstellar)
CREATE (nolan)-[:DIRECTED]->(interstellar)
CREATE (interstellar)-[:IN_GENRE]->(scifi)
CREATE (interstellar)-[:IN_GENRE]->(drama)

// Parasite (2019)
CREATE (parasite:Movie {
  title: 'Parasite',
  plot: 'Greed and class discrimination threaten the newly formed symbiotic relationship between the wealthy Park family and the destitute Kim clan.',
  year: 2019,
  released: '2019-05-30',
  countries: ['South Korea'],
  languages: ['Korean', 'English']
})
CREATE (songkangho:Actor {name: 'Song Kang-ho', born: 1967})
CREATE (choiwooshik:Actor {name: 'Choi Woo-shik', born: 1990})
CREATE (parksodam:Actor {name: 'Park So-dam', born: 1991})
CREATE (bongjoonho:Director {name: 'Bong Joon-ho', born: 1969})
CREATE (songkangho)-[:ACTED_IN {roles: ['Ki-taek']}]->(parasite)
CREATE (choiwooshik)-[:ACTED_IN {roles: ['Ki-woo']}]->(parasite)
CREATE (parksodam)-[:ACTED_IN {roles: ['Ki-jung']}]->(parasite)
CREATE (bongjoonho)-[:DIRECTED]->(parasite)
CREATE (parasite)-[:IN_GENRE]->(thriller)
CREATE (parasite)-[:IN_GENRE]->(drama)
CREATE (parasite)-[:IN_GENRE]->(comedy)

// Fight Club (1999)
CREATE (fightclub:Movie {
  title: 'Fight Club',
  plot: 'An insomniac office worker and a devil-may-care soapmaker form an underground fight club that evolves into something much more.',
  year: 1999,
  released: '1999-10-15',
  countries: ['USA', 'Germany'],
  languages: ['English']
})
CREATE (brad:Actor {name: 'Brad Pitt', born: 1963})
CREATE (edward:Actor {name: 'Edward Norton', born: 1969})
CREATE (helena:Actor {name: 'Helena Bonham Carter', born: 1966})
CREATE (fincher:Director {name: 'David Fincher', born: 1962})
CREATE (brad)-[:ACTED_IN {roles: ['Tyler Durden']}]->(fightclub)
CREATE (edward)-[:ACTED_IN {roles: ['Narrator']}]->(fightclub)
CREATE (helena)-[:ACTED_IN {roles: ['Marla Singer']}]->(fightclub)
CREATE (fincher)-[:DIRECTED]->(fightclub)
CREATE (fightclub)-[:IN_GENRE]->(drama)
CREATE (fightclub)-[:IN_GENRE]->(thriller)

// ============================================================================
// 사용자 및 평점 생성
// ============================================================================
CREATE (user1:User {name: 'Alice', userId: 'user001'})
CREATE (user2:User {name: 'Bob', userId: 'user002'})
CREATE (user3:User {name: 'Charlie', userId: 'user003'})
CREATE (user4:User {name: 'Diana', userId: 'user004'})
CREATE (user5:User {name: 'Eve', userId: 'user005'})

// 사용자 평점
CREATE (user1)-[:RATED {rating: 5.0}]->(matrix)
CREATE (user1)-[:RATED {rating: 4.5}]->(inception)
CREATE (user1)-[:RATED {rating: 5.0}]->(interstellar)
CREATE (user2)-[:RATED {rating: 5.0}]->(godfather)
CREATE (user2)-[:RATED {rating: 4.0}]->(pulp)
CREATE (user2)-[:RATED {rating: 4.5}]->(darkknight)
CREATE (user3)-[:RATED {rating: 4.5}]->(forrest)
CREATE (user3)-[:RATED {rating: 5.0}]->(titanic)
CREATE (user3)-[:RATED {rating: 4.0}]->(parasite)
CREATE (user4)-[:RATED {rating: 5.0}]->(matrix)
CREATE (user4)-[:RATED {rating: 5.0}]->(darkknight)
CREATE (user4)-[:RATED {rating: 4.5}]->(fightclub)
CREATE (user5)-[:RATED {rating: 4.0}]->(inception)
CREATE (user5)-[:RATED {rating: 5.0}]->(parasite)
CREATE (user5)-[:RATED {rating: 4.5}]->(pulp);
"""


def load_data(uri: str, username: str, password: str) -> bool:
    """
    Neo4j에 영화 데이터를 로드합니다.

    Args:
        uri: Neo4j 연결 URI
        username: Neo4j 사용자명
        password: Neo4j 비밀번호

    Returns:
        bool: 로드 성공 여부
    """
    print(f"🔌 Neo4j 연결 중...")
    print(f"   URI: {uri}")
    print()

    try:
        driver = GraphDatabase.driver(uri, auth=(username, password))
        driver.verify_connectivity()
        print("✅ 연결 성공!")
        print()

        print("📦 데이터 로드 중...")

        with driver.session() as session:
            # Cypher 쿼리 실행 (세미콜론으로 분리된 각 문장 실행)
            statements = [s.strip() for s in MOVIE_DATA.split(';') if s.strip()]

            for i, statement in enumerate(statements):
                # 주석 제거
                lines = [line for line in statement.split('\n')
                        if line.strip() and not line.strip().startswith('//')]
                clean_statement = '\n'.join(lines)

                if clean_statement:
                    session.run(clean_statement)

            print("✅ 데이터 로드 완료!")
            print()

            # 로드된 데이터 확인
            print("📊 로드된 데이터 통계:")

            result = session.run("MATCH (m:Movie) RETURN count(m) as count")
            print(f"   - 영화: {result.single()['count']}개")

            result = session.run("MATCH (a:Actor) RETURN count(a) as count")
            print(f"   - 배우: {result.single()['count']}명")

            result = session.run("MATCH (d:Director) RETURN count(d) as count")
            print(f"   - 감독: {result.single()['count']}명")

            result = session.run("MATCH (g:Genre) RETURN count(g) as count")
            print(f"   - 장르: {result.single()['count']}개")

            result = session.run("MATCH (u:User) RETURN count(u) as count")
            print(f"   - 사용자: {result.single()['count']}명")

            result = session.run("MATCH ()-[r:ACTED_IN]->() RETURN count(r) as count")
            print(f"   - 출연 관계: {result.single()['count']}개")

            result = session.run("MATCH ()-[r:RATED]->() RETURN count(r) as count")
            print(f"   - 평점: {result.single()['count']}개")

        driver.close()
        return True

    except ServiceUnavailable:
        print("❌ Neo4j 서버에 연결할 수 없습니다.")
        print("   Neo4j가 실행 중인지 확인하세요.")
        return False

    except AuthError:
        print("❌ 인증 실패: 비밀번호를 확인하세요.")
        return False

    except Exception as e:
        print(f"❌ 오류 발생: {e}")
        return False


def show_sample_data(uri: str, username: str, password: str):
    """
    로드된 샘플 데이터를 표시합니다.
    """
    print()
    print("🎬 로드된 영화 목록:")
    print("-" * 60)

    try:
        driver = GraphDatabase.driver(uri, auth=(username, password))

        with driver.session() as session:
            result = session.run("""
                MATCH (m:Movie)
                OPTIONAL MATCH (m)<-[:ACTED_IN]-(a:Actor)
                OPTIONAL MATCH (m)<-[:DIRECTED]-(d:Director)
                OPTIONAL MATCH (m)-[:IN_GENRE]->(g:Genre)
                RETURN m.title as title, m.year as year,
                       collect(DISTINCT a.name)[0..3] as actors,
                       collect(DISTINCT d.name)[0] as director,
                       collect(DISTINCT g.name) as genres
                ORDER BY m.year DESC
            """)

            for record in result:
                title = record['title']
                year = record['year']
                actors = ', '.join(record['actors']) if record['actors'] else 'N/A'
                director = record['director'] or 'N/A'
                genres = ', '.join(record['genres']) if record['genres'] else 'N/A'

                print(f"📽️  {title} ({year})")
                print(f"    감독: {director}")
                print(f"    출연: {actors}")
                print(f"    장르: {genres}")
                print()

        driver.close()

    except Exception as e:
        print(f"❌ 오류: {e}")


if __name__ == "__main__":
    print("=" * 60)
    print("Neo4j 영화 데이터 로드")
    print("=" * 60)
    print()

    # 커맨드라인 인자로 비밀번호를 받을 수 있음
    password = LOCAL_NEO4J_PASSWORD
    if len(sys.argv) > 1:
        password = sys.argv[1]
        print(f"ℹ️  커맨드라인에서 비밀번호를 사용합니다.")
        print()

    # 데이터 로드
    success = load_data(LOCAL_NEO4J_URI, LOCAL_NEO4J_USERNAME, password)

    if success:
        show_sample_data(LOCAL_NEO4J_URI, LOCAL_NEO4J_USERNAME, password)

    print("=" * 60)
    sys.exit(0 if success else 1)
