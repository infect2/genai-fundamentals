# SKILL.md

이 문서는 프로젝트에서 사용된 기술 스택과 학습할 수 있는 핵심 개념들을 정리합니다.

## 기술 스택 개요

```
┌─────────────────────────────────────────────────────────────┐
│                      Frontend / Client                       │
│                   (curl, Swagger UI, etc.)                  │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                     REST API Layer                          │
│                  FastAPI + Uvicorn (ASGI)                   │
│              api_server.py (Endpoints)                      │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                   Business Logic Layer                      │
│              graph_rag_service.py (Service)                 │
│                                                             │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐ │
│  │  LangChain  │  │   OpenAI    │  │  Session Manager    │ │
│  │    Chain    │  │    LLM      │  │  (History)          │ │
│  └─────────────┘  └─────────────┘  └─────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    Data Layer                               │
│                 Neo4j Graph Database                        │
│              (Nodes, Relationships, Cypher)                 │
└─────────────────────────────────────────────────────────────┘
```

## 핵심 기술 스택

### 1. Neo4j (그래프 데이터베이스)
| 항목 | 설명 |
|------|------|
| 역할 | 영화, 배우, 감독 등의 관계형 데이터 저장 |
| 쿼리 언어 | Cypher |
| Python 드라이버 | `neo4j`, `langchain-neo4j` |

**학습 포인트:**
- 그래프 데이터 모델링 (Node, Relationship, Property)
- Cypher 쿼리 문법 (MATCH, WHERE, RETURN)
- 벡터 인덱스를 활용한 유사도 검색

### 2. OpenAI (LLM)
| 항목 | 설명 |
|------|------|
| 모델 | GPT-4o |
| 용도 | 자연어→Cypher 변환, 답변 생성 |
| 임베딩 | text-embedding-ada-002 |

**학습 포인트:**
- Temperature 파라미터의 역할
- 프롬프트 엔지니어링 (Few-shot learning)
- 토큰 스트리밍

### 3. LangChain (LLM 프레임워크)
| 항목 | 설명 |
|------|------|
| 주요 컴포넌트 | Chain, Prompt, Memory, Callback |
| 사용 모듈 | `langchain-openai`, `langchain-neo4j` |

**학습 포인트:**
- GraphCypherQAChain 구조
- PromptTemplate 작성법
- ChatMessageHistory를 활용한 대화 관리

### 4. FastAPI (웹 프레임워크)
| 항목 | 설명 |
|------|------|
| 서버 | Uvicorn (ASGI) |
| 특징 | 비동기 지원, 자동 API 문서화 |

**학습 포인트:**
- Pydantic을 활용한 데이터 검증
- StreamingResponse로 SSE 구현
- 의존성 주입 패턴

### 5. neo4j-graphrag (GraphRAG 라이브러리)
| 항목 | 설명 |
|------|------|
| 제공 기능 | Retriever, Embedder, GraphRAG 파이프라인 |
| Retriever 종류 | VectorRetriever, VectorCypherRetriever, Text2CypherRetriever |

**학습 포인트:**
- RAG (Retrieval-Augmented Generation) 개념
- 벡터 검색과 그래프 탐색의 결합
- Text-to-Cypher 변환 기법

## 학습 로드맵

### Level 1: 기초
```
1. Python 기초
   └── 환경 변수, 패키지 관리, 비동기 프로그래밍

2. Neo4j 기초
   └── 그래프 개념 이해
   └── Cypher 쿼리 기초 (MATCH, CREATE, RETURN)
   └── Neo4j Browser 사용법

3. OpenAI API 기초
   └── API 키 설정
   └── Chat Completion API 호출
   └── Temperature, max_tokens 파라미터
```

### Level 2: 중급
```
4. 벡터 검색 이해
   └── 임베딩이란?
   └── 유사도 검색 (Cosine Similarity)
   └── Neo4j 벡터 인덱스

5. RAG 파이프라인 구축
   └── Retriever 구현
   └── Context 주입
   └── 답변 생성

6. LangChain 활용
   └── Chain 개념
   └── Prompt Template
   └── Memory 관리
```

### Level 3: 고급
```
7. GraphRAG 최적화
   └── Few-shot 프롬프트 설계
   └── 스키마 정보 활용
   └── 쿼리 정확도 향상

8. 프로덕션 배포
   └── FastAPI 서버 구축
   └── 스트리밍 응답 구현
   └── 세션 관리
   └── 에러 핸들링
```

## 파일별 학습 순서

| 순서 | 파일 | 학습 내용 |
|------|------|----------|
| 1 | `vector_retriever.py` | 기본 벡터 검색 |
| 2 | `vector_rag.py` | RAG 파이프라인 구축 |
| 3 | `vector_cypher_rag.py` | 벡터 + Cypher 결합 |
| 4 | `text2cypher_rag.py` | 자연어→Cypher 변환 |
| 5 | `graph_rag_service.py` | 서비스 클래스 설계 |
| 6 | `api_server.py` | REST API 구현 |

## 핵심 개념 용어집

| 용어 | 설명 |
|------|------|
| **RAG** | Retrieval-Augmented Generation. 검색 결과를 LLM 컨텍스트에 주입하여 답변 생성 |
| **GraphRAG** | 그래프 데이터베이스를 활용한 RAG |
| **Embedding** | 텍스트를 고차원 벡터로 변환한 것 |
| **Vector Index** | 벡터 유사도 검색을 위한 인덱스 |
| **Cypher** | Neo4j의 그래프 쿼리 언어 |
| **Few-shot Learning** | 소수의 예시를 통해 모델의 출력을 유도하는 기법 |
| **SSE** | Server-Sent Events. 서버→클라이언트 단방향 스트리밍 |
| **Chain** | LangChain에서 여러 컴포넌트를 연결한 처리 파이프라인 |

## 참고 자료

### 공식 문서
- [Neo4j Documentation](https://neo4j.com/docs/)
- [LangChain Documentation](https://python.langchain.com/docs/)
- [OpenAI API Reference](https://platform.openai.com/docs/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)

### 강의
- [Neo4j GraphAcademy - GenAI Fundamentals](https://graphacademy.neo4j.com/courses/genai-fundamentals)

### 추가 학습
- [Cypher Query Language](https://neo4j.com/docs/cypher-manual/)
- [LangChain Neo4j Integration](https://python.langchain.com/docs/integrations/graphs/neo4j_cypher)
