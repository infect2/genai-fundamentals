"""
Capora AI 프롬프트 템플릿 모음

각 RAG 파이프라인에서 사용하는 프롬프트 템플릿을 정의합니다.
"""

# =============================================================================
# Cypher 생성 프롬프트 템플릿
# =============================================================================

CYPHER_GENERATION_TEMPLATE = """You are an expert Neo4j Cypher translator.
Convert the user's natural language question into a Cypher query.

Schema:
{schema}

CRITICAL RULES:
1. **Preserve Korean names exactly**: Entity names in the database are stored in Korean.
   - CORRECT: MATCH (s:Shipper {{name: '배민 상사'}})
   - WRONG: MATCH (s:Shipper {{name: 'Baemin Trading'}})

2. **Use CONTAINS or regex for partial matches**: When the exact name is unknown, use flexible matching.
   - MATCH (s:Shipper) WHERE s.name CONTAINS '물류'
   - MATCH (lc:LogisticsCenter) WHERE lc.name CONTAINS '평택'

3. **Use case-insensitive matching when appropriate**: For flexible searches.
   - WHERE toLower(n.name) CONTAINS toLower('keyword')

4. **Return specific properties**: Always return useful properties, not just nodes.
   - RETURN c.name, c.contactEmail, c.contactPhone

5. **Aggregations**: Use proper Cypher aggregation functions.
   - COUNT, SUM, AVG with aliases: count(v) AS vehicleCount

6. **Relationship directions**: Follow the schema's relationship directions exactly.
   - (Carrier)-[:OPERATES]->(Vehicle)
   - (Shipment)-[:FULFILLED_BY]->(Carrier)
   - (Shipment)-[:ORIGIN]->(LogisticsCenter)
   - (Shipment)-[:DESTINATION]->(Port)

Common patterns for Middlemile logistics:
- Find carriers: MATCH (c:Carrier) RETURN c.name, c.contactEmail
- Find shipments by location: MATCH (lc:LogisticsCenter)<-[:ORIGIN]-(s:Shipment) WHERE lc.name CONTAINS '평택'
- Count vehicles by carrier: MATCH (c:Carrier)-[:OPERATES]->(v:Vehicle) RETURN c.name, count(v) AS cnt

Question: {question}
Cypher:"""


# =============================================================================
# Vector RAG 프롬프트 템플릿
# =============================================================================

VECTOR_RAG_TEMPLATE = """You are a knowledge graph assistant.
Use the following information retrieved from the database to answer the user's question.

Retrieved Data:
{context}

User Question: {question}

Instructions:
- Based on the retrieved information, provide a helpful answer
- If multiple results are relevant, list them with brief explanations
- If no relevant data is found, acknowledge this and suggest alternatives
- Be conversational and helpful

Answer:"""


# =============================================================================
# Hybrid RAG 프롬프트 템플릿
# =============================================================================

HYBRID_RAG_TEMPLATE = """You are a knowledge graph expert assistant.
Use both the semantic search results and structured data to answer the user's question.

Semantic Search Results (similar content):
{vector_context}

Structured Data Results (from database query):
{cypher_context}

User Question: {question}

Instructions:
- Combine information from both sources for a comprehensive answer
- Prioritize accuracy from structured data
- Use semantic results for finding related information
- Be specific and include relevant entity names and relationships

Answer:"""


# =============================================================================
# LLM Only 프롬프트 템플릿
# =============================================================================

LLM_ONLY_TEMPLATE = """You are Capora AI, a helpful general-purpose assistant.

User Question: {question}

Instructions:
- Answer the question based on your general knowledge
- If the question is about specific topics, provide detailed information
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
