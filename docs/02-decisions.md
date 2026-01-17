# Architecture Decision Log

프로젝트의 주요 아키텍처 결정 사항을 기록합니다.

---

## ADR-001: LangChain 기반 GraphRAG 구현

**날짜:** 2025-01-10
**상태:** Accepted
**결정자:** Team

### Context
GraphRAG 파이프라인을 구현하기 위한 프레임워크 선택이 필요했습니다.

### Options
1. **LangChain + langchain-neo4j** - 성숙한 생태계, 풍부한 문서
2. **neo4j-graphrag** - Neo4j 공식 라이브러리, 네이티브 통합
3. **직접 구현** - 완전한 제어, 높은 개발 비용

### Decision
LangChain과 langchain-neo4j를 메인 프레임워크로 채택

### Rationale
- GraphCypherQAChain으로 Text2Cypher 기능 즉시 사용 가능
- 세션/메모리 관리 내장
- 스트리밍 응답 지원
- 커뮤니티 지원 및 문서화 우수

### Consequences
- **장점:** 빠른 개발, 안정적인 기능
- **단점:** LangChain 버전 의존성 관리 필요

---

## ADR-002: FastAPI REST API 서버 구조

**날짜:** 2025-01-11
**상태:** Accepted
**결정자:** Team

### Context
클라이언트와 GraphRAG 서비스 간 통신을 위한 API 서버가 필요했습니다.

### Options
1. **FastAPI** - 비동기 지원, 자동 문서화
2. **Flask** - 간단하고 익숙함
3. **Django REST Framework** - 풀스택 기능

### Decision
FastAPI 채택

### Rationale
- 비동기 처리로 스트리밍 응답 지원
- Pydantic 모델로 요청/응답 검증
- Swagger UI 자동 생성
- 높은 성능

### Consequences
- **장점:** SSE 스트리밍 구현 용이, API 문서 자동화
- **단점:** Chainlit과 uvicorn 버전 충돌 이슈 (0.25.0으로 고정하여 해결)

---

## ADR-003: 듀얼 클라이언트 전략 (Streamlit + Chainlit)

**날짜:** 2025-01-12
**상태:** Accepted
**결정자:** Team

### Context
사용자 인터페이스로 웹 클라이언트가 필요했습니다.

### Options
1. **Streamlit만** - 데이터 앱에 강점
2. **Chainlit만** - 채팅 인터페이스 특화
3. **둘 다** - 다양한 사용자 경험 제공

### Decision
Streamlit과 Chainlit 모두 구현

### Rationale
- Streamlit: 간단한 사이드바 설정, 빠른 프로토타이핑
- Chainlit: 슬래시 명령어, 액션 버튼, 네이티브 채팅 경험
- 학습 목적으로 두 프레임워크 비교 가능

### Consequences
- **장점:** 사용자 선택권 제공, 프레임워크 비교 학습
- **단점:** 유지보수 포인트 증가

---

## ADR-004: Server-Sent Events (SSE) 스트리밍

**날짜:** 2025-01-13
**상태:** Accepted
**결정자:** Team

### Context
LLM 응답을 실시간으로 사용자에게 전달하는 방법이 필요했습니다.

### Options
1. **SSE (Server-Sent Events)** - 단방향 스트리밍
2. **WebSocket** - 양방향 통신
3. **Long Polling** - 간단하지만 비효율적

### Decision
SSE 방식 채택

### Rationale
- LLM 응답은 서버→클라이언트 단방향으로 충분
- HTTP 기반으로 구현 간단
- FastAPI StreamingResponse와 자연스러운 통합

### Consequences
- **장점:** 구현 단순, ChatGPT 스타일 UX
- **단점:** 클라이언트에서 SSE 파싱 로직 필요

---

## ADR-005: Docker 기반 배포

**날짜:** 2025-01-14
**상태:** Accepted
**결정자:** Team

### Context
일관된 실행 환경과 쉬운 배포를 위한 컨테이너화가 필요했습니다.

### Options
1. **Docker + Docker Compose** - 컨테이너 오케스트레이션
2. **직접 설치** - 환경 의존성 문제
3. **Kubernetes** - 오버엔지니어링

### Decision
Docker + Docker Compose 채택

### Rationale
- 로컬 개발과 배포 환경 일치
- 멀티 스테이지 빌드로 이미지 최적화
- Health check로 안정성 확보

### Consequences
- **장점:** 환경 독립성, 쉬운 배포
- **단점:** Docker 지식 필요, 로컬 Neo4j 연결 시 host.docker.internal 사용 필요

---

## ADR-006: 로컬 Neo4j 지원

**날짜:** 2025-01-17
**상태:** Accepted
**결정자:** Team

### Context
클라우드 Neo4j 외에 로컬 Neo4j Desktop 연결이 필요했습니다.

### Options
1. **클라우드만 지원** - 설정 간단
2. **로컬만 지원** - 네트워크 비용 없음
3. **둘 다 지원** - 유연성 제공

### Decision
클라우드 및 로컬 Neo4j 모두 지원

### Rationale
- 개발 시 로컬 환경에서 빠른 테스트
- 프로덕션에서 클라우드 사용 가능
- .env 파일로 쉽게 전환

### Consequences
- **장점:** 환경에 따른 유연한 선택
- **단점:** APOC 플러그인 설치 필요, Docker에서 host.docker.internal 사용

### Implementation Notes
```bash
# 로컬 Neo4j 연결 (.env)
NEO4J_URI="neo4j://host.docker.internal:7687"
NEO4J_PASSWORD="your-password"

# 클라우드 Neo4j 연결 (.env)
NEO4J_URI="neo4j+s://xxx.databases.neo4j.io"
NEO4J_PASSWORD="cloud-password"
```

---

## ADR-007: 세션 기반 대화 컨텍스트 관리

**날짜:** 2025-01-15
**상태:** Accepted
**결정자:** Team

### Context
다중 사용자 환경에서 대화 컨텍스트를 관리하는 방법이 필요했습니다.

### Options
1. **인메모리 세션** - 간단, 서버 재시작 시 초기화
2. **Redis 세션** - 영속성, 추가 인프라 필요
3. **DB 저장** - 완전한 영속성, 복잡도 증가

### Decision
인메모리 세션 관리 (LangChain ConversationBufferMemory)

### Rationale
- 학습 프로젝트 목적에 적합
- 추가 인프라 불필요
- LangChain 메모리 기능 활용

### Consequences
- **장점:** 간단한 구현, 의존성 최소화
- **단점:** 서버 재시작 시 대화 기록 손실

---

## 템플릿

새로운 결정 사항 추가 시 아래 템플릿을 사용하세요:

```markdown
## ADR-XXX: [제목]

**날짜:** YYYY-MM-DD
**상태:** Proposed | Accepted | Deprecated | Superseded
**결정자:** [이름/팀]

### Context
[결정이 필요한 배경 설명]

### Options
1. **옵션1** - 설명
2. **옵션2** - 설명
3. **옵션3** - 설명

### Decision
[선택한 옵션]

### Rationale
[선택 이유]

### Consequences
- **장점:**
- **단점:**
```
