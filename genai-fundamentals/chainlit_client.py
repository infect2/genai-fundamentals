# =============================================================================
# GraphRAG Chainlit Client
# =============================================================================
# REST API와 연동하는 대화형 클라이언트
# - 채팅 형식의 대화 이력 표시
# - 스트리밍 응답 지원
# - 컨텍스트 리셋 토글
# =============================================================================

import chainlit as cl
import requests
import json
import uuid
from typing import Optional

# -----------------------------------------------------------------------------
# 설정
# -----------------------------------------------------------------------------
API_BASE_URL = "http://localhost:8000"

# -----------------------------------------------------------------------------
# 채팅 시작 이벤트
# -----------------------------------------------------------------------------
@cl.on_chat_start
async def on_chat_start():
    """
    채팅 세션이 시작될 때 호출됩니다.
    세션 ID를 생성하고 설정을 초기화합니다.
    """
    # 세션 ID 생성
    session_id = str(uuid.uuid4())[:8]
    cl.user_session.set("session_id", session_id)

    # 기본 설정
    cl.user_session.set("reset_context", False)
    cl.user_session.set("use_streaming", True)

    # API 연결 확인
    try:
        response = requests.get(f"{API_BASE_URL}/", timeout=5)
        if response.status_code == 200:
            data = response.json()
            version = data.get("version", "N/A")
            await cl.Message(
                content=f"🎬 **GraphRAG Movie Chat**에 오신 것을 환영합니다!\n\n"
                        f"📡 API 서버 연결됨 (v{version})\n"
                        f"🔑 세션 ID: `{session_id}`\n\n"
                        f"영화에 대해 질문해보세요!"
            ).send()
        else:
            await cl.Message(
                content="⚠️ API 서버에 연결되었지만 응답이 올바르지 않습니다."
            ).send()
    except requests.exceptions.ConnectionError:
        await cl.Message(
            content="❌ API 서버에 연결할 수 없습니다.\n\n"
                    "서버가 실행 중인지 확인하세요:\n"
                    "```bash\n"
                    "docker-compose up -d\n"
                    "# 또는\n"
                    "python -m genai-fundamentals.api_server\n"
                    "```"
        ).send()
    except Exception as e:
        await cl.Message(content=f"❌ 오류가 발생했습니다: {str(e)}").send()

# -----------------------------------------------------------------------------
# 설정 변경 액션
# -----------------------------------------------------------------------------
@cl.action_callback("toggle_reset_context")
async def toggle_reset_context(action: cl.Action):
    """컨텍스트 리셋 토글"""
    current = cl.user_session.get("reset_context", False)
    cl.user_session.set("reset_context", not current)
    status = "활성화" if not current else "비활성화"
    await cl.Message(content=f"🔄 컨텍스트 리셋이 **{status}** 되었습니다.").send()

@cl.action_callback("toggle_streaming")
async def toggle_streaming(action: cl.Action):
    """스트리밍 모드 토글"""
    current = cl.user_session.get("use_streaming", True)
    cl.user_session.set("use_streaming", not current)
    status = "활성화" if not current else "비활성화"
    await cl.Message(content=f"📡 스트리밍 모드가 **{status}** 되었습니다.").send()

@cl.action_callback("reset_session")
async def reset_session(action: cl.Action):
    """세션 초기화"""
    session_id = cl.user_session.get("session_id")
    try:
        requests.post(f"{API_BASE_URL}/reset/{session_id}", timeout=5)
        new_session_id = str(uuid.uuid4())[:8]
        cl.user_session.set("session_id", new_session_id)
        await cl.Message(
            content=f"🗑️ 세션이 초기화되었습니다.\n새 세션 ID: `{new_session_id}`"
        ).send()
    except Exception as e:
        await cl.Message(content=f"❌ 세션 초기화 실패: {str(e)}").send()

@cl.action_callback("show_settings")
async def show_settings(action: cl.Action):
    """현재 설정 표시"""
    session_id = cl.user_session.get("session_id")
    reset_context = cl.user_session.get("reset_context", False)
    use_streaming = cl.user_session.get("use_streaming", True)

    await cl.Message(
        content=f"⚙️ **현재 설정**\n\n"
                f"- 세션 ID: `{session_id}`\n"
                f"- 컨텍스트 리셋: {'✅ 활성화' if reset_context else '❌ 비활성화'}\n"
                f"- 스트리밍 모드: {'✅ 활성화' if use_streaming else '❌ 비활성화'}",
        actions=[
            cl.Action(name="toggle_reset_context", payload={}, label="🔄 컨텍스트 리셋 토글"),
            cl.Action(name="toggle_streaming", payload={}, label="📡 스트리밍 토글"),
            cl.Action(name="reset_session", payload={}, label="🗑️ 세션 초기화"),
        ]
    ).send()

# -----------------------------------------------------------------------------
# 스트리밍 응답 처리
# -----------------------------------------------------------------------------
async def stream_response(query: str, session_id: str, reset: bool, msg: cl.Message) -> dict:
    """
    SSE 스트리밍 응답을 처리합니다.
    """
    metadata = {}
    full_response = ""

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
                            token = data.get('content', '')
                            full_response += token
                            await msg.stream_token(token)
                        elif data.get('type') == 'done':
                            break
                        elif data.get('type') == 'error':
                            error_msg = data.get('message', 'Unknown error')
                            full_response += f"\n\n❌ 오류: {error_msg}"
                            await msg.stream_token(f"\n\n❌ 오류: {error_msg}")
                            break
                    except json.JSONDecodeError:
                        continue

    except requests.exceptions.ConnectionError:
        full_response = "❌ API 서버에 연결할 수 없습니다."
        await msg.stream_token(full_response)
    except Exception as e:
        full_response = f"❌ 오류가 발생했습니다: {str(e)}"
        await msg.stream_token(full_response)

    metadata['answer'] = full_response
    return metadata

# -----------------------------------------------------------------------------
# 일반 응답 처리
# -----------------------------------------------------------------------------
async def get_response(query: str, session_id: str, reset: bool) -> dict:
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
            return {
                "answer": f"❌ 오류: HTTP {response.status_code}",
                "cypher": "",
                "context": []
            }

    except requests.exceptions.ConnectionError:
        return {
            "answer": "❌ API 서버에 연결할 수 없습니다.",
            "cypher": "",
            "context": []
        }
    except Exception as e:
        return {
            "answer": f"❌ 오류가 발생했습니다: {str(e)}",
            "cypher": "",
            "context": []
        }

# -----------------------------------------------------------------------------
# 메시지 수신 이벤트
# -----------------------------------------------------------------------------
@cl.on_message
async def on_message(message: cl.Message):
    """
    사용자 메시지를 수신하고 처리합니다.
    """
    query = message.content.strip()

    # 명령어 처리
    if query.lower() in ["/settings", "/설정", "설정"]:
        await show_settings(None)
        return

    if query.lower() in ["/reset", "/초기화", "초기화"]:
        await reset_session(None)
        return

    if query.lower() in ["/help", "/도움말", "도움말"]:
        await cl.Message(
            content="📖 **사용 가능한 명령어**\n\n"
                    "- `/settings` 또는 `설정` - 현재 설정 보기\n"
                    "- `/reset` 또는 `초기화` - 세션 초기화\n"
                    "- `/help` 또는 `도움말` - 도움말 보기\n\n"
                    "영화에 대해 자유롭게 질문하세요!"
        ).send()
        return

    # 세션 정보 가져오기
    session_id = cl.user_session.get("session_id")
    reset_context = cl.user_session.get("reset_context", False)
    use_streaming = cl.user_session.get("use_streaming", True)

    # 응답 메시지 생성
    msg = cl.Message(content="")
    await msg.send()

    if use_streaming:
        # 스트리밍 모드
        result = await stream_response(query, session_id, reset_context, msg)
    else:
        # 일반 모드
        result = await get_response(query, session_id, reset_context)
        msg.content = result.get("answer", "")
        await msg.update()

    # 메타데이터가 있으면 표시
    cypher = result.get("cypher", "")
    context = result.get("context", [])

    if cypher or context:
        # 상세 정보를 별도 메시지로 표시
        elements = []

        if cypher:
            elements.append(
                cl.Text(name="Cypher Query", content=cypher, display="inline")
            )

        if context and len(context) > 0:
            context_str = json.dumps(context[:5], indent=2, ensure_ascii=False)
            elements.append(
                cl.Text(name="Context (Top 5)", content=context_str, display="inline")
            )

        if elements:
            await cl.Message(
                content="🔍 **상세 정보**",
                elements=elements,
                actions=[
                    cl.Action(name="show_settings", payload={}, label="⚙️ 설정"),
                ]
            ).send()

# -----------------------------------------------------------------------------
# 세션 종료 이벤트
# -----------------------------------------------------------------------------
@cl.on_chat_end
async def on_chat_end():
    """
    채팅 세션이 종료될 때 호출됩니다.
    """
    session_id = cl.user_session.get("session_id")
    if session_id:
        try:
            requests.post(f"{API_BASE_URL}/reset/{session_id}", timeout=5)
        except:
            pass
