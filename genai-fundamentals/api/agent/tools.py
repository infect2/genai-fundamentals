"""
Agent Tools Module

ReAct Agent에서 사용하는 도구들을 정의합니다.
기존 GraphRAGService의 메서드를 LangChain Tool 형태로 래핑합니다.
"""

from typing import TYPE_CHECKING
from langchain_core.tools import tool

from .prompts import TOOL_DESCRIPTIONS

if TYPE_CHECKING:
    from ..service import GraphRAGService


def create_agent_tools(service: "GraphRAGService"):
    """
    GraphRAGService를 래핑하는 LangChain 도구들을 생성합니다.

    Args:
        service: GraphRAGService 인스턴스

    Returns:
        LangChain Tool 리스트
    """

    @tool
    def cypher_query(query: str) -> str:
        """Execute a natural language query that gets converted to Cypher.
        Use for specific entity/relationship queries like 'Which actors appeared in The Matrix?'.
        Returns structured data from Neo4j.

        Args:
            query: Natural language question about movies, actors, directors, or genres
        """
        try:
            result = service.query(query, force_route="cypher")
            output_parts = [f"Answer: {result.answer}"]
            if result.cypher:
                output_parts.append(f"Cypher Query: {result.cypher}")
            if result.context:
                output_parts.append(f"Context: {result.context[:5]}")  # Limit context
            return "\n".join(output_parts)
        except Exception as e:
            return f"Error executing cypher query: {str(e)}"

    @tool
    def vector_search(query: str, top_k: int = 5) -> str:
        """Search for movies based on semantic similarity of their plots.
        Use for queries like 'Find sad movies' or 'Movies similar to Inception'.
        Returns movies with similar themes/plots.

        Args:
            query: Natural language description of what kind of movies to find
            top_k: Number of similar movies to return (default: 5)
        """
        try:
            result = service.query(query, force_route="vector")
            output_parts = [f"Answer: {result.answer}"]
            if result.context:
                output_parts.append(f"Found movies: {result.context[:top_k]}")
            return "\n".join(output_parts)
        except Exception as e:
            return f"Error executing vector search: {str(e)}"

    @tool
    def hybrid_search(query: str, top_k: int = 3) -> str:
        """Combine structured Cypher queries with semantic vector search.
        Use for complex queries needing both exact data and thematic similarity.
        Example: 'Highly rated sci-fi movies with interesting plots'

        Args:
            query: Complex question requiring both structured and semantic search
            top_k: Number of vector search results to include (default: 3)
        """
        try:
            result = service.query(query, force_route="hybrid")
            output_parts = [f"Answer: {result.answer}"]
            if result.cypher:
                output_parts.append(f"Cypher Query: {result.cypher}")
            if result.context:
                output_parts.append(f"Context: {result.context[:6]}")  # Limit context
            return "\n".join(output_parts)
        except Exception as e:
            return f"Error executing hybrid search: {str(e)}"

    @tool
    def get_schema() -> str:
        """Get the Neo4j database schema including node types, relationships, and properties.
        Use when you need to understand what data is available in the database.
        """
        try:
            schema = service.get_schema()
            return f"Database Schema:\n{schema}"
        except Exception as e:
            return f"Error getting schema: {str(e)}"

    @tool
    def user_memory(request: str) -> str:
        """Store or recall user's personal information like car number, phone number, email, etc.
        Use this tool when the user wants to:
        - Store information: "내 차번호는 59거5249이다", "Remember my email is test@example.com"
        - Recall information: "내 차번호 뭐지?", "What's my email?"

        Args:
            request: Natural language request to store or recall user information
        """
        try:
            result = service.query(request, force_route="memory")
            return f"Memory: {result.answer}"
        except Exception as e:
            return f"Error with user memory: {str(e)}"

    return [cypher_query, vector_search, hybrid_search, get_schema, user_memory]
