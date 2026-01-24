"""
LLM Provider Factory Module

환경변수 LLM_PROVIDER에 따라 적절한 LLM 및 Embeddings 인스턴스를 생성합니다.

지원 프로바이더:
- openai: OpenAI API (기본값)
- bedrock: AWS Bedrock
- azure: Azure OpenAI
- google: Google Vertex AI

사용 예:
    from genai_fundamentals.tools.llm_provider import (
        create_langchain_llm,
        create_langchain_embeddings,
        create_neo4j_llm,
        create_neo4j_embeddings,
        get_token_tracker,
    )

    # LangChain 레이어 (API 서버용)
    llm = create_langchain_llm()
    embeddings = create_langchain_embeddings()

    # neo4j-graphrag 레이어 (exercises/solutions용)
    neo4j_llm = create_neo4j_llm()
    neo4j_embedder = create_neo4j_embeddings()

    # 토큰 추적
    with get_token_tracker() as tracker:
        result = chain.invoke(...)
    usage = tracker.get_usage()
"""

import os
import warnings
from enum import Enum
from typing import Optional, Any
from contextlib import contextmanager
from dataclasses import dataclass, field

from dotenv import load_dotenv
load_dotenv()


# =============================================================================
# Provider Enum
# =============================================================================

class LLMProvider(Enum):
    OPENAI = "openai"
    BEDROCK = "bedrock"
    AZURE = "azure"
    GOOGLE = "google"


def get_provider() -> LLMProvider:
    """LLM_PROVIDER 환경변수를 읽어 LLMProvider enum을 반환합니다."""
    provider_str = os.getenv("LLM_PROVIDER", "openai").lower()
    try:
        return LLMProvider(provider_str)
    except ValueError:
        warnings.warn(
            f"Unknown LLM_PROVIDER '{provider_str}', falling back to 'openai'"
        )
        return LLMProvider.OPENAI


# =============================================================================
# Embedding Dimensions
# =============================================================================

EMBEDDING_DIMENSIONS = {
    "openai": {
        "text-embedding-ada-002": 1536,
        "text-embedding-3-small": 1536,
        "text-embedding-3-large": 3072,
    },
    "azure": {
        "text-embedding-ada-002": 1536,
        "text-embedding-3-small": 1536,
        "text-embedding-3-large": 3072,
    },
    "bedrock": {
        "amazon.titan-embed-text-v2:0": 1024,
        "amazon.titan-embed-text-v1": 1536,
        "cohere.embed-english-v3": 1024,
    },
    "google": {
        "text-embedding-004": 768,
        "textembedding-gecko@003": 768,
    },
}

# Neo4j moviePlots 인덱스는 OpenAI text-embedding-ada-002 (1536차원)으로 생성됨
_NEO4J_INDEX_DIMENSION = 1536


def get_current_embedding_dimension() -> int:
    """현재 프로바이더/모델의 임베딩 차원을 반환합니다."""
    provider = get_provider()
    if provider == LLMProvider.OPENAI:
        model = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-ada-002")
        return EMBEDDING_DIMENSIONS["openai"].get(model, 1536)
    elif provider == LLMProvider.AZURE:
        model = os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT", "text-embedding-ada-002")
        return EMBEDDING_DIMENSIONS["azure"].get(model, 1536)
    elif provider == LLMProvider.BEDROCK:
        model = os.getenv("BEDROCK_EMBEDDING_MODEL_ID", "amazon.titan-embed-text-v2:0")
        return EMBEDDING_DIMENSIONS["bedrock"].get(model, 1024)
    elif provider == LLMProvider.GOOGLE:
        model = os.getenv("VERTEX_EMBEDDING_MODEL", "text-embedding-004")
        return EMBEDDING_DIMENSIONS["google"].get(model, 768)
    return 1536


def check_embedding_dimension_compatibility():
    """임베딩 차원이 Neo4j 인덱스와 호환되는지 확인하고 경고를 출력합니다."""
    dim = get_current_embedding_dimension()
    if dim != _NEO4J_INDEX_DIMENSION:
        provider = get_provider()
        warnings.warn(
            f"[LLM Provider] Current embedding dimension ({dim}) does not match "
            f"Neo4j moviePlots index dimension ({_NEO4J_INDEX_DIMENSION}). "
            f"Provider '{provider.value}' may require re-indexing the vector store. "
            f"Vector search results may be incorrect.",
            stacklevel=2
        )


# =============================================================================
# Router Model Names
# =============================================================================

_ROUTER_MODELS = {
    LLMProvider.OPENAI: "gpt-4o-mini",
    LLMProvider.BEDROCK: "anthropic.claude-3-haiku-20240307-v1:0",
    LLMProvider.AZURE: None,  # Uses AZURE_OPENAI_DEPLOYMENT (same deployment)
    LLMProvider.GOOGLE: "gemini-1.5-flash",
}


def get_router_model_name() -> str:
    """라우터용 경량 모델명을 반환합니다."""
    provider = get_provider()
    if provider == LLMProvider.AZURE:
        return os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o")
    return _ROUTER_MODELS.get(provider, "gpt-4o-mini")


# =============================================================================
# LangChain Layer (API Server)
# =============================================================================

def create_langchain_llm(
    model_name: Optional[str] = None,
    temperature: float = 0,
    streaming: bool = False,
    **kwargs
):
    """
    LangChain BaseChatModel 인스턴스를 생성합니다.

    Args:
        model_name: 모델명 (None이면 프로바이더별 기본값 사용)
        temperature: LLM temperature
        streaming: 스트리밍 모드
        **kwargs: 프로바이더별 추가 인자

    Returns:
        BaseChatModel 인스턴스
    """
    provider = get_provider()

    if provider == LLMProvider.OPENAI:
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=model_name or os.getenv("OPENAI_MODEL", "gpt-4o"),
            temperature=temperature,
            streaming=streaming,
            **kwargs
        )

    elif provider == LLMProvider.BEDROCK:
        from langchain_aws import ChatBedrockConverse
        return ChatBedrockConverse(
            model=model_name or os.getenv("BEDROCK_MODEL_ID", "anthropic.claude-3-5-sonnet-20241022-v2:0"),
            temperature=temperature,
            region_name=os.getenv("AWS_REGION", "us-east-1"),
            **kwargs
        )

    elif provider == LLMProvider.AZURE:
        from langchain_openai import AzureChatOpenAI
        return AzureChatOpenAI(
            azure_deployment=model_name or os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o"),
            azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT", ""),
            api_key=os.getenv("AZURE_OPENAI_API_KEY", ""),
            api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-15-preview"),
            temperature=temperature,
            streaming=streaming,
            **kwargs
        )

    elif provider == LLMProvider.GOOGLE:
        from langchain_google_vertexai import ChatVertexAI
        return ChatVertexAI(
            model_name=model_name or os.getenv("VERTEX_MODEL", "gemini-1.5-pro"),
            project=os.getenv("GOOGLE_PROJECT_ID"),
            location=os.getenv("GOOGLE_LOCATION", "us-central1"),
            temperature=temperature,
            streaming=streaming,
            **kwargs
        )

    raise ValueError(f"Unsupported provider: {provider}")


def create_langchain_embeddings(**kwargs):
    """
    LangChain Embeddings 인스턴스를 생성합니다.

    Returns:
        Embeddings 인스턴스
    """
    provider = get_provider()

    if provider == LLMProvider.OPENAI:
        from langchain_openai import OpenAIEmbeddings
        return OpenAIEmbeddings(
            model=os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-ada-002"),
            **kwargs
        )

    elif provider == LLMProvider.BEDROCK:
        from langchain_aws import BedrockEmbeddings
        return BedrockEmbeddings(
            model_id=os.getenv("BEDROCK_EMBEDDING_MODEL_ID", "amazon.titan-embed-text-v2:0"),
            region_name=os.getenv("AWS_REGION", "us-east-1"),
            **kwargs
        )

    elif provider == LLMProvider.AZURE:
        from langchain_openai import AzureOpenAIEmbeddings
        return AzureOpenAIEmbeddings(
            azure_deployment=os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT", "text-embedding-ada-002"),
            azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT", ""),
            api_key=os.getenv("AZURE_OPENAI_API_KEY", ""),
            api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-15-preview"),
            **kwargs
        )

    elif provider == LLMProvider.GOOGLE:
        from langchain_google_vertexai import VertexAIEmbeddings
        return VertexAIEmbeddings(
            model_name=os.getenv("VERTEX_EMBEDDING_MODEL", "text-embedding-004"),
            project=os.getenv("GOOGLE_PROJECT_ID"),
            location=os.getenv("GOOGLE_LOCATION", "us-central1"),
            **kwargs
        )

    raise ValueError(f"Unsupported provider: {provider}")


# =============================================================================
# neo4j-graphrag Layer (exercises/solutions)
# =============================================================================

def create_neo4j_llm(
    model_name: Optional[str] = None,
    model_params: Optional[dict] = None,
    **kwargs
):
    """
    neo4j-graphrag LLMInterface 인스턴스를 생성합니다.

    Args:
        model_name: 모델명 (None이면 프로바이더별 기본값)
        model_params: 모델 파라미터 (temperature 등)
        **kwargs: 추가 인자

    Returns:
        LLMInterface 구현체
    """
    provider = get_provider()

    if provider == LLMProvider.OPENAI:
        from neo4j_graphrag.llm import OpenAILLM
        return OpenAILLM(
            model_name=model_name or os.getenv("OPENAI_MODEL", "gpt-4o"),
            model_params=model_params or {},
            **kwargs
        )

    elif provider == LLMProvider.BEDROCK:
        return BedrockNeo4jLLM(
            model_id=model_name or os.getenv("BEDROCK_MODEL_ID", "anthropic.claude-3-5-sonnet-20241022-v2:0"),
            region_name=os.getenv("AWS_REGION", "us-east-1"),
            model_params=model_params or {},
            **kwargs
        )

    elif provider == LLMProvider.AZURE:
        from neo4j_graphrag.llm import OpenAILLM
        return OpenAILLM(
            model_name=model_name or os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o"),
            model_params=model_params or {},
            api_key=os.getenv("AZURE_OPENAI_API_KEY", ""),
            base_url=f"{os.getenv('AZURE_OPENAI_ENDPOINT', '').rstrip('/')}/openai/deployments/{os.getenv('AZURE_OPENAI_DEPLOYMENT', 'gpt-4o')}",
            **kwargs
        )

    elif provider == LLMProvider.GOOGLE:
        return VertexAINeo4jLLM(
            model_name=model_name or os.getenv("VERTEX_MODEL", "gemini-1.5-pro"),
            project=os.getenv("GOOGLE_PROJECT_ID"),
            location=os.getenv("GOOGLE_LOCATION", "us-central1"),
            model_params=model_params or {},
            **kwargs
        )

    raise ValueError(f"Unsupported provider: {provider}")


def create_neo4j_embeddings(model: Optional[str] = None, **kwargs):
    """
    neo4j-graphrag Embedder 인스턴스를 생성합니다.

    Args:
        model: 모델명 (None이면 프로바이더별 기본값)
        **kwargs: 추가 인자

    Returns:
        Embedder 구현체
    """
    provider = get_provider()

    if provider == LLMProvider.OPENAI:
        from neo4j_graphrag.embeddings.openai import OpenAIEmbeddings
        return OpenAIEmbeddings(
            model=model or os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-ada-002"),
            **kwargs
        )

    elif provider == LLMProvider.BEDROCK:
        return BedrockNeo4jEmbeddings(
            model_id=model or os.getenv("BEDROCK_EMBEDDING_MODEL_ID", "amazon.titan-embed-text-v2:0"),
            region_name=os.getenv("AWS_REGION", "us-east-1"),
            **kwargs
        )

    elif provider == LLMProvider.AZURE:
        from neo4j_graphrag.embeddings.openai import OpenAIEmbeddings
        return OpenAIEmbeddings(
            model=model or os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT", "text-embedding-ada-002"),
            api_key=os.getenv("AZURE_OPENAI_API_KEY", ""),
            base_url=f"{os.getenv('AZURE_OPENAI_ENDPOINT', '').rstrip('/')}/openai/deployments/{os.getenv('AZURE_OPENAI_EMBEDDING_DEPLOYMENT', 'text-embedding-ada-002')}",
            **kwargs
        )

    elif provider == LLMProvider.GOOGLE:
        return VertexAINeo4jEmbeddings(
            model_name=model or os.getenv("VERTEX_EMBEDDING_MODEL", "text-embedding-004"),
            project=os.getenv("GOOGLE_PROJECT_ID"),
            location=os.getenv("GOOGLE_LOCATION", "us-central1"),
            **kwargs
        )

    raise ValueError(f"Unsupported provider: {provider}")


# =============================================================================
# Token Tracking
# =============================================================================

@dataclass
class GenericTokenUsage:
    """프로바이더 독립적 토큰 사용량 데이터 클래스"""
    total_tokens: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_cost: float = 0.0


class GenericTokenTracker:
    """OpenAI callback을 사용할 수 없는 프로바이더용 토큰 추적기"""

    def __init__(self):
        self._usage = GenericTokenUsage()
        self._callback_handler = _TokenTrackingCallbackHandler(self)

    @property
    def callback_handler(self):
        """LangChain 콜백 핸들러를 반환합니다."""
        return self._callback_handler

    def get_usage(self) -> GenericTokenUsage:
        return self._usage

    # OpenAI callback과 동일한 속성 인터페이스
    @property
    def total_tokens(self) -> int:
        return self._usage.total_tokens

    @property
    def prompt_tokens(self) -> int:
        return self._usage.prompt_tokens

    @property
    def completion_tokens(self) -> int:
        return self._usage.completion_tokens

    @property
    def total_cost(self) -> float:
        return self._usage.total_cost

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


class _TokenTrackingCallbackHandler:
    """LangChain on_llm_end에서 토큰 사용량을 추출하는 콜백 핸들러"""

    def __init__(self, tracker: GenericTokenTracker):
        self._tracker = tracker

    def on_llm_end(self, response, **kwargs):
        """LLM 응답 완료 시 토큰 사용량 추출"""
        if hasattr(response, "llm_output") and response.llm_output:
            usage = response.llm_output.get("token_usage", {})
            if usage:
                self._tracker._usage.total_tokens += usage.get("total_tokens", 0)
                self._tracker._usage.prompt_tokens += usage.get("prompt_tokens", 0)
                self._tracker._usage.completion_tokens += usage.get("completion_tokens", 0)


@contextmanager
def get_token_tracker():
    """
    프로바이더에 따라 적절한 토큰 추적기를 반환하는 컨텍스트 매니저.

    OpenAI/Azure: get_openai_callback() 사용 (정확한 비용 계산)
    Bedrock/Google: GenericTokenTracker 사용 (토큰 수만 추적, 비용은 0.0)

    사용 예:
        with get_token_tracker() as tracker:
            result = chain.invoke(...)
        print(tracker.total_tokens)
        print(tracker.total_cost)
    """
    provider = get_provider()

    if provider in (LLMProvider.OPENAI, LLMProvider.AZURE):
        from langchain_community.callbacks import get_openai_callback
        with get_openai_callback() as cb:
            yield cb
    else:
        tracker = GenericTokenTracker()
        yield tracker


# =============================================================================
# Bedrock Custom Wrappers (neo4j-graphrag 미지원)
# =============================================================================

class BedrockNeo4jLLM:
    """
    AWS Bedrock용 neo4j-graphrag LLMInterface 구현.
    boto3 converse API를 사용합니다.
    """

    def __init__(
        self,
        model_id: str = "anthropic.claude-3-5-sonnet-20241022-v2:0",
        region_name: str = "us-east-1",
        model_params: Optional[dict] = None,
        **kwargs
    ):
        self.model_id = model_id
        self.region_name = region_name
        self.model_params = model_params or {}

        import boto3
        self._client = boto3.client(
            "bedrock-runtime",
            region_name=region_name,
        )

    def invoke(self, input: str) -> "LLMResponse":
        """동기 LLM 호출"""
        inference_config = {}
        if "temperature" in self.model_params:
            inference_config["temperature"] = self.model_params["temperature"]
        if "max_tokens" in self.model_params:
            inference_config["maxTokens"] = self.model_params["max_tokens"]

        kwargs = {
            "modelId": self.model_id,
            "messages": [
                {"role": "user", "content": [{"text": input}]}
            ],
        }
        if inference_config:
            kwargs["inferenceConfig"] = inference_config

        response = self._client.converse(**kwargs)
        content = response["output"]["message"]["content"][0]["text"]
        return _LLMResponse(content=content)

    async def ainvoke(self, input: str) -> "LLMResponse":
        """비동기 LLM 호출 (동기를 래핑)"""
        import asyncio
        return await asyncio.to_thread(self.invoke, input)


class BedrockNeo4jEmbeddings:
    """
    AWS Bedrock용 neo4j-graphrag Embedder 구현.
    boto3 invoke_model API를 사용합니다.
    """

    def __init__(
        self,
        model_id: str = "amazon.titan-embed-text-v2:0",
        region_name: str = "us-east-1",
        **kwargs
    ):
        self.model_id = model_id
        self.region_name = region_name

        import boto3
        self._client = boto3.client(
            "bedrock-runtime",
            region_name=region_name,
        )

    def embed_query(self, text: str) -> list:
        """단일 텍스트의 임베딩 벡터를 반환합니다."""
        import json
        body = json.dumps({"inputText": text})
        response = self._client.invoke_model(
            modelId=self.model_id,
            body=body,
            contentType="application/json",
            accept="application/json",
        )
        response_body = json.loads(response["body"].read())
        return response_body["embedding"]


# =============================================================================
# Vertex AI Custom Wrappers (neo4j-graphrag 미지원)
# =============================================================================

class VertexAINeo4jLLM:
    """
    Google Vertex AI용 neo4j-graphrag LLMInterface 구현.
    """

    def __init__(
        self,
        model_name: str = "gemini-1.5-pro",
        project: Optional[str] = None,
        location: str = "us-central1",
        model_params: Optional[dict] = None,
        **kwargs
    ):
        self.model_name = model_name
        self.project = project
        self.location = location
        self.model_params = model_params or {}

        from google.cloud import aiplatform
        aiplatform.init(project=project, location=location)

        import vertexai
        from vertexai.generative_models import GenerativeModel
        vertexai.init(project=project, location=location)
        self._model = GenerativeModel(model_name)

    def invoke(self, input: str) -> "LLMResponse":
        """동기 LLM 호출"""
        from vertexai.generative_models import GenerationConfig

        config_kwargs = {}
        if "temperature" in self.model_params:
            config_kwargs["temperature"] = self.model_params["temperature"]
        if "max_tokens" in self.model_params:
            config_kwargs["max_output_tokens"] = self.model_params["max_tokens"]

        config = GenerationConfig(**config_kwargs) if config_kwargs else None
        response = self._model.generate_content(input, generation_config=config)
        return _LLMResponse(content=response.text)

    async def ainvoke(self, input: str) -> "LLMResponse":
        """비동기 LLM 호출 (동기를 래핑)"""
        import asyncio
        return await asyncio.to_thread(self.invoke, input)


class VertexAINeo4jEmbeddings:
    """
    Google Vertex AI용 neo4j-graphrag Embedder 구현.
    """

    def __init__(
        self,
        model_name: str = "text-embedding-004",
        project: Optional[str] = None,
        location: str = "us-central1",
        **kwargs
    ):
        self.model_name = model_name
        self.project = project
        self.location = location

        from vertexai.language_models import TextEmbeddingModel
        import vertexai
        vertexai.init(project=project, location=location)
        self._model = TextEmbeddingModel.from_pretrained(model_name)

    def embed_query(self, text: str) -> list:
        """단일 텍스트의 임베딩 벡터를 반환합니다."""
        embeddings = self._model.get_embeddings([text])
        return embeddings[0].values


# =============================================================================
# Internal Helpers
# =============================================================================

class _LLMResponse:
    """neo4j-graphrag LLMInterface 응답 객체"""
    def __init__(self, content: str):
        self.content = content
