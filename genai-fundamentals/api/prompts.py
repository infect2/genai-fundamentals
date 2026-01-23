"""
GraphRAG 프롬프트 템플릿 모음

각 RAG 파이프라인에서 사용하는 프롬프트 템플릿을 정의합니다.
"""

# =============================================================================
# Cypher 생성 프롬프트 템플릿
# =============================================================================

CYPHER_GENERATION_TEMPLATE = """You are an expert Neo4j Cypher translator.
Convert the user's natural language question into a Cypher query.

Schema:
{schema}

Important notes:
- Movie titles with articles are stored as "Title, The" format (e.g., "Matrix, The", "Godfather, The")
- Use case-insensitive matching when possible

Examples:
Q: Which actors appeared in The Matrix?
Cypher: MATCH (a:Actor)-[:ACTED_IN]->(m:Movie) WHERE m.title = 'Matrix, The' RETURN a.name

Q: What movies did Tom Hanks star in?
Cypher: MATCH (a:Actor {{name: 'Tom Hanks'}})-[:ACTED_IN]->(m:Movie) RETURN m.title

Q: What genre is Toy Story?
Cypher: MATCH (m:Movie {{title: 'Toy Story'}})-[:IN_GENRE]->(g:Genre) RETURN g.name

Q: Who directed The Godfather?
Cypher: MATCH (d:Director)-[:DIRECTED]->(m:Movie) WHERE m.title = 'Godfather, The' RETURN d.name

Question: {question}
Cypher:"""


# =============================================================================
# Vector RAG 프롬프트 템플릿
# =============================================================================

VECTOR_RAG_TEMPLATE = """You are a movie recommendation assistant.
Use the following movie information retrieved from the database to answer the user's question.

Retrieved Movies:
{context}

User Question: {question}

Instructions:
- Based on the retrieved movie information, provide a helpful answer
- If multiple movies are relevant, list them with brief explanations
- If no relevant movies are found, acknowledge this and suggest alternatives
- Be conversational and helpful

Answer:"""


# =============================================================================
# Hybrid RAG 프롬프트 템플릿
# =============================================================================

HYBRID_RAG_TEMPLATE = """You are a movie expert assistant.
Use both the semantic search results and structured data to answer the user's question.

Semantic Search Results (similar movies by plot/theme):
{vector_context}

Structured Data Results (from database query):
{cypher_context}

User Question: {question}

Instructions:
- Combine information from both sources for a comprehensive answer
- Prioritize accuracy from structured data
- Use semantic results for recommendations and comparisons
- Be specific and include movie titles, actors, directors when relevant

Answer:"""


# =============================================================================
# LLM Only 프롬프트 템플릿
# =============================================================================

LLM_ONLY_TEMPLATE = """You are a helpful general-purpose assistant.

User Question: {question}

Instructions:
- Answer the question based on your general knowledge
- If the question is about movies, provide detailed movie-related information
- If the question is about other topics (math, science, coding, etc.), answer helpfully
- If the question is a greeting or casual conversation, respond appropriately
- Keep responses concise and helpful
- Respond in the same language as the user's question

Answer:"""


# =============================================================================
# 메모리 추출 프롬프트 템플릿
# =============================================================================

MEMORY_EXTRACT_TEMPLATE = """사용자의 메시지에서 저장할 정보를 추출하세요.

메시지: {message}

JSON 형식으로 응답하세요:
{{"action": "store" 또는 "recall", "key": "정보 종류 (예: 차번호, 이메일, 전화번호)", "value": "저장할 값 (store인 경우만)"}}

store 예시:
- "내 차번호는 59구8426이야" → {{"action": "store", "key": "차번호", "value": "59구8426"}}
- "내 이메일은 test@email.com이야 기억해" → {{"action": "store", "key": "이메일", "value": "test@email.com"}}

recall 예시:
- "내 차번호 뭐지?" → {{"action": "recall", "key": "차번호", "value": ""}}
- "내 이메일 알려줘" → {{"action": "recall", "key": "이메일", "value": ""}}
"""
