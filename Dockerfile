# =============================================================================
# GraphRAG API Server Dockerfile
# =============================================================================
# 이 Dockerfile은 GraphRAG REST API 서버를 컨테이너로 패키징합니다.
#
# 빌드: docker build -t graphrag-api .
# 실행: docker run -p 8000:8000 --env-file .env graphrag-api
# =============================================================================

# -----------------------------------------------------------------------------
# Stage 1: Base image
# -----------------------------------------------------------------------------
FROM python:3.11-slim AS base

# 환경 변수 설정
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# 작업 디렉토리 설정
WORKDIR /app

# -----------------------------------------------------------------------------
# Stage 2: Dependencies
# -----------------------------------------------------------------------------
FROM base AS dependencies

# 시스템 패키지 설치 (빌드에 필요한 패키지)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# requirements.txt 복사 및 의존성 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# -----------------------------------------------------------------------------
# Stage 3: Production
# -----------------------------------------------------------------------------
FROM base AS production

# 의존성 복사 (이전 스테이지에서)
COPY --from=dependencies /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=dependencies /usr/local/bin /usr/local/bin

# 애플리케이션 코드 복사
COPY genai-fundamentals/ ./genai-fundamentals/

# 비root 사용자 생성 (보안)
RUN useradd --create-home --shell /bin/bash appuser && \
    chown -R appuser:appuser /app
USER appuser

# 포트 노출
EXPOSE 8000

# 헬스체크
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/')" || exit 1

# 서버 실행
CMD ["python", "-m", "uvicorn", "genai-fundamentals.api.server:app", "--host", "0.0.0.0", "--port", "8000"]
