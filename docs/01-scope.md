# Project Scope: GraphRAG Fundamentals

> **Single Source of Truth for Goals & Constraints**
>
> 이 문서는 프로젝트의 목표와 제약 조건에 대한 유일한 진실의 원천(SSOT)입니다.
> 모든 의사결정은 이 문서를 기준으로 평가되어야 합니다.

---

## 1. Project Goals

### 1.1 Primary Goals (Must Have)

| ID | Goal | Success Criteria |
|----|------|------------------|
| G1 | GraphRAG 학습 환경 제공 | Vector/Cypher/Text2Cypher RAG 파이프라인 실습 가능 |
| G2 | 자연어로 영화 데이터 질의 | "매트릭스 출연 배우는?" 질문에 정확한 답변 반환 |
| G3 | 실시간 응답 스트리밍 | 토큰 단위 응답이 1초 이내 시작 |
| G4 | 로컬/클라우드 Neo4j 지원 | .env 설정만으로 환경 전환 가능 |

### 1.2 Secondary Goals (Should Have)

| ID | Goal | Success Criteria |
|----|------|------------------|
| G5 | 다중 클라이언트 지원 | Streamlit, Chainlit 모두 동작 |
| G6 | Docker 배포 | `docker-compose up` 한 번으로 실행 |
| G7 | 세션별 대화 컨텍스트 유지 | 연속 질문에 이전 맥락 반영 |

### 1.3 Non-Goals (Out of Scope)

| ID | Explicitly Excluded | Reason |
|----|---------------------|--------|
| NG1 | 사용자 인증/인가 | 학습용 프로젝트, 보안 범위 제외 |
| NG2 | 프로덕션 수준 가용성 | 개발/학습 환경 전용 |
| NG3 | 다중 데이터베이스 지원 | 단일 Neo4j 인스턴스로 충분 |
| NG4 | 커스텀 임베딩 모델 | OpenAI 임베딩으로 한정 |
| NG5 | 실시간 데이터 동기화 | 정적 영화 데이터셋 사용 |
| NG6 | 다국어 지원 | 한국어/영어만 지원 |

---

## 2. Constraints

### 2.1 Technical Constraints

| ID | Constraint | Impact |
|----|------------|--------|
| TC1 | Python 3.11+ 필수 | 최신 타입 힌트 및 asyncio 기능 활용 |
| TC2 | Neo4j APOC 플러그인 필수 | langchain-neo4j의 스키마 조회 의존성 |
| TC3 | OpenAI API 키 필수 | GPT-4 및 Embeddings 사용 |
| TC4 | Docker Desktop (배포 시) | 컨테이너 실행 환경 |

### 2.2 Resource Constraints

| ID | Constraint | Limit |
|----|------------|-------|
| RC1 | OpenAI API 비용 | 학습용으로 최소 호출 유지 |
| RC2 | Neo4j 메모리 | 로컬 환경 1GB 이상 권장 |
| RC3 | 동시 세션 수 | 인메모리 관리로 ~100 세션 |

### 2.3 Dependency Constraints

| Package | Version Constraint | Reason |
|---------|-------------------|--------|
| fastapi | 0.115.3 ~ 0.115.x | Chainlit 호환성 |
| uvicorn | 0.25.x | Chainlit 호환성 |
| langchain | 0.3.x | API 안정성 |
| neo4j | 5.x | Neo4j 서버 호환 |

---

## 3. Assumptions

| ID | Assumption | Risk if Invalid |
|----|------------|-----------------|
| A1 | 사용자가 Python 환경 구성 가능 | 설치 가이드 제공 필요 |
| A2 | Neo4j Desktop 또는 AuraDB 접근 가능 | 샘플 데이터 로드 스크립트 제공 |
| A3 | OpenAI API 키 보유 | 대체 LLM 미지원 |
| A4 | 인터넷 연결 가능 | 오프라인 모드 미지원 |

---

## 4. Success Metrics

### 4.1 Functional Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| 쿼리 정확도 | 90%+ | 테스트 쿼리 셋 기준 |
| API 응답 시작 시간 | < 2초 | 스트리밍 첫 토큰 기준 |
| 에러율 | < 5% | 유효한 쿼리 기준 |

### 4.2 Learning Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| 코드 가독성 | 상세 주석 | 모든 함수 docstring |
| 실습 완료 가능 | 100% | 모든 exercise 파일 실행 |

---

## 5. Boundaries

### 5.1 Data Boundary

```
포함: 영화, 배우, 감독, 장르, 사용자 평점
제외: 리뷰 텍스트, 이미지, 비디오, 외부 API 데이터
```

### 5.2 Feature Boundary

```
포함: 질의응답, 스트리밍, 세션 관리, 컨텍스트 리셋
제외: 데이터 수정(CRUD), 추천 시스템, 분석 대시보드
```

### 5.3 Integration Boundary

```
포함: Neo4j, OpenAI
제외: 다른 그래프 DB, 다른 LLM 제공자, 외부 검색 엔진
```

---

## 6. Risks & Mitigations

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| OpenAI API 비용 초과 | Medium | High | 캐싱, 요청 제한 |
| Neo4j 연결 실패 | Low | High | 연결 테스트 스크립트 제공 |
| 의존성 버전 충돌 | Medium | Medium | requirements.txt 버전 고정 |
| Cypher 생성 오류 | Medium | Medium | Few-shot 예제 제공 |

---

## 7. Change Log

| Date | Version | Change | Author |
|------|---------|--------|--------|
| 2025-01-10 | 1.0 | 초기 스코프 정의 | Team |
| 2025-01-17 | 1.1 | 로컬 Neo4j 지원 추가 | Team |
| 2025-01-18 | 1.2 | SSOT 형식으로 재작성 | Team |

---

## 8. Approval

> 이 문서의 변경은 팀 리뷰 후 승인되어야 합니다.
>
> **최종 승인일:** 2025-01-18
