# =============================================================================
# GraphRAG Streamlit Client
# =============================================================================
# REST API와 연동하는 대화형 클라이언트
# - 채팅 형식의 대화 이력 표시
# - 스트리밍 응답 지원
# - 컨텍스트 리셋 토글
# =============================================================================

import streamlit as st
import requests
import json
import uuid
from typing import Generator

# -----------------------------------------------------------------------------
# 설정
# -----------------------------------------------------------------------------
API_BASE_URL = "http://localhost:8000"

# -----------------------------------------------------------------------------
# 페이지 설정
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="GraphRAG Chat",
    page_icon="🎬",
    layout="wide"
)

# -----------------------------------------------------------------------------
# 세션 상태 초기화
# -----------------------------------------------------------------------------
if "messages" not in st.session_state:
    st.session_state.messages = []

if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())[:8]

# -----------------------------------------------------------------------------
# 사이드바 설정
# -----------------------------------------------------------------------------
with st.sidebar:
    st.title("⚙️ 설정")

    # 세션 ID 표시
    st.text_input("세션 ID", value=st.session_state.session_id, disabled=True)

    # 컨텍스트 리셋 토글
    reset_context = st.toggle(
        "컨텍스트 리셋",
        value=False,
        help="활성화하면 각 질문마다 이전 대화 맥락을 초기화합니다."
    )

    # 스트리밍 토글
    use_streaming = st.toggle(
        "스트리밍 모드",
        value=True,
        help="응답을 실시간으로 스트리밍합니다."
    )

    st.divider()

    # 대화 초기화 버튼
    if st.button("🗑️ 대화 기록 삭제", use_container_width=True):
        st.session_state.messages = []
        # 서버 세션도 리셋
        try:
            requests.post(f"{API_BASE_URL}/reset/{st.session_state.session_id}")
        except:
            pass
        st.rerun()

    # 새 세션 시작 버튼
    if st.button("🔄 새 세션 시작", use_container_width=True):
        st.session_state.messages = []
        st.session_state.session_id = str(uuid.uuid4())[:8]
        st.rerun()

    st.divider()

    # API 상태 확인
    st.subheader("📡 API 상태")
    try:
        response = requests.get(f"{API_BASE_URL}/", timeout=5)
        if response.status_code == 200:
            data = response.json()
            st.success(f"✅ 연결됨 (v{data.get('version', 'N/A')})")
        else:
            st.error("❌ 연결 실패")
    except requests.exceptions.ConnectionError:
        st.error("❌ API 서버에 연결할 수 없습니다")
    except Exception as e:
        st.error(f"❌ 오류: {str(e)}")

# -----------------------------------------------------------------------------
# 메인 화면
# -----------------------------------------------------------------------------
st.title("🎬 GraphRAG Movie Chat")
st.caption("Neo4j 그래프 데이터베이스 기반 영화 질의응답 시스템")

# -----------------------------------------------------------------------------
# 스트리밍 응답 처리 함수
# -----------------------------------------------------------------------------
def stream_response(query: str, session_id: str, reset: bool) -> Generator[str, None, dict]:
    """
    SSE 스트리밍 응답을 처리하고 토큰을 yield합니다.
    마지막에 메타데이터(cypher, context)를 반환합니다.
    """
    metadata = {}

    try:
        response = requests.post(
            f"{API_BASE_URL}/query",
            json={
                "query": query,
                "session_id": session_id,
                "reset_context": reset,
                "stream": True
            },
            stream=True,
            timeout=60
        )

        for line in response.iter_lines():
            if line:
                line_str = line.decode('utf-8')
                if line_str.startswith('data: '):
                    try:
                        data = json.loads(line_str[6:])

                        if data.get('type') == 'metadata':
                            metadata['cypher'] = data.get('cypher', '')
                            metadata['context'] = data.get('context', [])
                        elif data.get('type') == 'token':
                            yield data.get('content', '')
                        elif data.get('type') == 'done':
                            break
                        elif data.get('type') == 'error':
                            yield f"\n\n❌ 오류: {data.get('message', 'Unknown error')}"
                            break
                    except json.JSONDecodeError:
                        continue
    except requests.exceptions.ConnectionError:
        yield "❌ API 서버에 연결할 수 없습니다."
    except Exception as e:
        yield f"❌ 오류가 발생했습니다: {str(e)}"

    return metadata

# -----------------------------------------------------------------------------
# 일반 응답 처리 함수
# -----------------------------------------------------------------------------
def get_response(query: str, session_id: str, reset: bool) -> dict:
    """
    일반(non-streaming) API 호출을 수행합니다.
    """
    try:
        response = requests.post(
            f"{API_BASE_URL}/query",
            json={
                "query": query,
                "session_id": session_id,
                "reset_context": reset,
                "stream": False
            },
            timeout=60
        )

        if response.status_code == 200:
            return response.json()
        else:
            return {"answer": f"❌ 오류: HTTP {response.status_code}", "cypher": "", "context": []}

    except requests.exceptions.ConnectionError:
        return {"answer": "❌ API 서버에 연결할 수 없습니다.", "cypher": "", "context": []}
    except Exception as e:
        return {"answer": f"❌ 오류가 발생했습니다: {str(e)}", "cypher": "", "context": []}

# -----------------------------------------------------------------------------
# 대화 이력 표시
# -----------------------------------------------------------------------------
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

        # 어시스턴트 메시지에 메타데이터 표시
        if message["role"] == "assistant" and "metadata" in message:
            with st.expander("🔍 상세 정보"):
                if message["metadata"].get("cypher"):
                    st.code(message["metadata"]["cypher"], language="cypher")
                if message["metadata"].get("context"):
                    st.json(message["metadata"]["context"][:5])  # 상위 5개만 표시

# -----------------------------------------------------------------------------
# 사용자 입력 처리
# -----------------------------------------------------------------------------
if prompt := st.chat_input("영화에 대해 질문하세요..."):
    # 사용자 메시지 추가
    st.session_state.messages.append({"role": "user", "content": prompt})

    # 사용자 메시지 표시
    with st.chat_message("user"):
        st.markdown(prompt)

    # 어시스턴트 응답
    with st.chat_message("assistant"):
        if use_streaming:
            # 스트리밍 모드
            response_placeholder = st.empty()
            full_response = ""
            metadata = {}

            # 스트리밍 응답 수신
            for token in stream_response(prompt, st.session_state.session_id, reset_context):
                full_response += token
                response_placeholder.markdown(full_response + "▌")

            response_placeholder.markdown(full_response)

            # 메타데이터 가져오기 (스트리밍에서는 별도 처리 필요)
            # 현재 구조에서는 generator의 return 값을 직접 받기 어려우므로
            # 메타데이터는 표시하지 않거나 별도 API 호출 필요

            st.session_state.messages.append({
                "role": "assistant",
                "content": full_response,
                "metadata": {}
            })
        else:
            # 일반 모드
            with st.spinner("생각 중..."):
                result = get_response(prompt, st.session_state.session_id, reset_context)

            st.markdown(result["answer"])

            # 메타데이터 표시
            if result.get("cypher") or result.get("context"):
                with st.expander("🔍 상세 정보"):
                    if result.get("cypher"):
                        st.code(result["cypher"], language="cypher")
                    if result.get("context"):
                        st.json(result["context"][:5])

            st.session_state.messages.append({
                "role": "assistant",
                "content": result["answer"],
                "metadata": {
                    "cypher": result.get("cypher", ""),
                    "context": result.get("context", [])
                }
            })

# -----------------------------------------------------------------------------
# 푸터
# -----------------------------------------------------------------------------
st.divider()
st.caption("Powered by Neo4j GraphRAG & LangChain | Built with Streamlit")
