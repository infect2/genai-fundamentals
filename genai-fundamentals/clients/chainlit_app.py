# =============================================================================
# GraphRAG Chainlit Client
# =============================================================================
# 이 파일은 GraphRAG API 서버와 통신하는 Chainlit 기반 웹 채팅 클라이언트입니다.
#
# 주요 기능:
# - 채팅 형식의 대화형 인터페이스 제공
# - 실시간 스트리밍 응답 지원 (Server-Sent Events)
# - 세션별 대화 컨텍스트 관리
# - 컨텍스트 리셋 토글 기능
# - 슬래시 명령어 지원 (/settings, /reset, /help)
# - 인라인 액션 버튼 지원
#
# 실행 방법:
#   chainlit run genai-fundamentals/chainlit_client.py --port 8502
#
# 사전 요구사항:
#   - GraphRAG API 서버가 실행 중이어야 함 (기본: http://localhost:8000)
#   - chainlit 패키지 설치 필요 (pip install chainlit)
# =============================================================================

# -----------------------------------------------------------------------------
# 의존성 임포트
# -----------------------------------------------------------------------------
import chainlit as cl                    # Chainlit 프레임워크 - 대화형 UI 구축
from chainlit.input_widget import Switch # 토글 스위치 위젯 (설정 UI용)
import requests                          # HTTP 요청 라이브러리 (API 통신)
import json                              # JSON 파싱/직렬화
import uuid                              # 고유 세션 ID 생성
from typing import Optional              # 타입 힌트

# -----------------------------------------------------------------------------
# 전역 설정
# -----------------------------------------------------------------------------
# API 서버의 기본 URL
# 로컬 개발 환경에서는 localhost:8000, 프로덕션에서는 실제 서버 URL로 변경
API_BASE_URL = "http://localhost:8000"

# -----------------------------------------------------------------------------
# Google OAuth 콜백
# -----------------------------------------------------------------------------
@cl.oauth_callback
def oauth_callback(
    provider_id: str,
    token: str,
    raw_user_data: dict[str, str],
    default_user: cl.User,
) -> Optional[cl.User]:
    """
    Google OAuth 인증 콜백입니다.

    사용자가 Google 로그인을 완료하면 Chainlit이 이 함수를 호출합니다.
    인증된 사용자 정보를 Chainlit User 객체로 반환합니다.

    Args:
        provider_id: OAuth 제공자 식별자 (예: "google")
        token: OAuth 액세스 토큰
        raw_user_data: Google에서 반환한 사용자 정보 딕셔너리
        default_user: Chainlit이 기본 생성한 User 객체

    Returns:
        cl.User: 인증된 사용자 객체 (None 반환 시 인증 거부)
    """
    if provider_id == "google":
        return cl.User(
            identifier=raw_user_data.get("email", ""),
            display_name=raw_user_data.get("name"),
            metadata={
                "email": raw_user_data.get("email"),
                "picture": raw_user_data.get("picture"),
                "provider": "google",
            },
        )
    return None


# -----------------------------------------------------------------------------
# 채팅 시작 이벤트 핸들러
# -----------------------------------------------------------------------------
@cl.on_chat_start
async def on_chat_start():
    """
    채팅 세션이 시작될 때 자동으로 호출되는 Chainlit 이벤트 핸들러입니다.

    이 함수는 다음 작업을 수행합니다:
    1. 새로운 세션 ID 생성 (8자리 UUID)
    2. 기본 설정값 초기화 (컨텍스트 리셋: False, 스트리밍: True)
    3. Chat Settings UI 구성 (토글 버튼 표시)
    4. API 서버 연결 상태 확인 및 환영 메시지 표시

    Notes:
        - cl.user_session은 Chainlit의 세션 스토리지로, 사용자별 데이터를 저장합니다.
        - Chat Settings UI는 화면 우측 상단의 설정 아이콘을 통해 접근할 수 있습니다.
    """
    # -------------------------------------------------------------------------
    # 세션 ID 생성
    # -------------------------------------------------------------------------
    # UUID v4를 생성하고 앞 8자리만 사용하여 짧고 고유한 세션 식별자 생성
    # 예: "a1b2c3d4"
    session_id = str(uuid.uuid4())[:8]
    cl.user_session.set("session_id", session_id)

    # -------------------------------------------------------------------------
    # 기본 설정 초기화
    # -------------------------------------------------------------------------
    # reset_context: True이면 매 질문마다 이전 대화 맥락을 무시하고 새로 시작
    #                False이면 이전 대화 맥락을 유지하여 연속적인 대화 가능
    cl.user_session.set("reset_context", False)

    # use_streaming: True이면 응답을 토큰 단위로 실시간 스트리밍 (SSE 방식)
    #                False이면 전체 응답이 완성된 후 한 번에 표시
    cl.user_session.set("use_streaming", True)

    # -------------------------------------------------------------------------
    # Chat Settings UI 구성
    # -------------------------------------------------------------------------
    # Chainlit의 ChatSettings를 사용하여 사용자가 설정을 변경할 수 있는 UI 생성
    # 설정 아이콘(⚙️)을 클릭하면 이 토글 버튼들이 표시됨
    settings = await cl.ChatSettings(
        [
            # 컨텍스트 리셋 토글 스위치
            Switch(
                id="reset_context",           # 설정 값의 키 (on_settings_update에서 사용)
                label="🔄 컨텍스트 리셋",      # UI에 표시되는 레이블
                initial=False,                # 초기값
                description="활성화하면 각 질문마다 이전 대화 맥락을 초기화합니다."
            ),
            # 스트리밍 모드 토글 스위치
            Switch(
                id="use_streaming",           # 설정 값의 키
                label="📡 스트리밍 모드",      # UI에 표시되는 레이블
                initial=True,                 # 초기값 (기본적으로 스트리밍 활성화)
                description="응답을 실시간으로 스트리밍합니다."
            ),
        ]
    ).send()  # .send()를 호출해야 UI가 실제로 렌더링됨

    # -------------------------------------------------------------------------
    # API 서버 연결 확인 및 환영 메시지 표시
    # -------------------------------------------------------------------------
    # -------------------------------------------------------------------------
    # 인증된 사용자 정보 조회
    # -------------------------------------------------------------------------
    user = cl.user_session.get("user")
    display_name = user.display_name or user.identifier if user else "Guest"

    try:
        # API 서버의 루트 엔드포인트(/)에 GET 요청을 보내 연결 상태 확인
        # timeout=5: 5초 내에 응답이 없으면 타임아웃 예외 발생
        response = requests.get(f"{API_BASE_URL}/", timeout=5)

        if response.status_code == 200:
            # 연결 성공: API 버전 정보를 포함한 환영 메시지 표시
            data = response.json()
            version = data.get("version", "N/A")  # API 버전 (없으면 "N/A")
            await cl.Message(
                content=f"🎬 **Capora AI powered by Ontology**에 오신 것을 환영합니다, {display_name}님!\n\n"
                        f"📡 API 서버 연결됨 (v{version})\n"
                        f"🔑 세션 ID: `{session_id}`\n\n"
                        f"무엇이든 물어보세요!"
            ).send()
        else:
            # HTTP 상태 코드가 200이 아닌 경우 (예: 500 Internal Server Error)
            await cl.Message(
                content="⚠️ API 서버에 연결되었지만 응답이 올바르지 않습니다."
            ).send()

    except requests.exceptions.ConnectionError:
        # 연결 실패: 서버가 실행 중이지 않거나 네트워크 문제
        # 사용자에게 서버 실행 방법 안내
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
        # 기타 예외 (타임아웃, JSON 파싱 오류 등)
        await cl.Message(content=f"❌ 오류가 발생했습니다: {str(e)}").send()

# -----------------------------------------------------------------------------
# Chat Settings UI 변경 이벤트 핸들러
# -----------------------------------------------------------------------------
@cl.on_settings_update
async def on_settings_update(settings):
    """
    Chat Settings UI에서 사용자가 설정을 변경할 때 호출되는 이벤트 핸들러입니다.

    사용자가 설정 패널의 토글 스위치를 변경하면 이 함수가 자동 호출됩니다.
    변경된 설정값을 세션에 저장하고, 변경 내용을 사용자에게 알립니다.

    Args:
        settings (dict): 변경된 설정값들을 담은 딕셔너리
                        예: {"reset_context": True, "use_streaming": False}

    Notes:
        - settings 딕셔너리의 키는 Switch의 id와 일치합니다.
        - .get() 메서드를 사용하여 키가 없는 경우 기본값을 반환합니다.
    """
    # 세션 스토리지에 새로운 설정값 저장
    cl.user_session.set("reset_context", settings.get("reset_context", False))
    cl.user_session.set("use_streaming", settings.get("use_streaming", True))

    # 사용자에게 표시할 상태 문자열 생성
    reset_status = "✅ 활성화" if settings.get("reset_context") else "❌ 비활성화"
    stream_status = "✅ 활성화" if settings.get("use_streaming") else "❌ 비활성화"

    # 설정 변경 확인 메시지 표시
    await cl.Message(
        content=f"⚙️ **설정이 변경되었습니다**\n\n"
                f"- 컨텍스트 리셋: {reset_status}\n"
                f"- 스트리밍 모드: {stream_status}"
    ).send()

# -----------------------------------------------------------------------------
# 액션 콜백 함수들 (인라인 버튼 클릭 시 호출)
# -----------------------------------------------------------------------------
# Chainlit의 Action 버튼을 클릭하면 해당 action_callback 데코레이터가 붙은 함수가 호출됩니다.
# 이를 통해 사용자가 버튼을 클릭하여 특정 기능을 실행할 수 있습니다.

@cl.action_callback("toggle_reset_context")
async def toggle_reset_context(action: cl.Action):
    """
    컨텍스트 리셋 설정을 토글하는 액션 콜백입니다.

    '🔄 컨텍스트 리셋 토글' 버튼을 클릭하면 호출됩니다.
    현재 설정값의 반대값으로 변경합니다.

    Args:
        action (cl.Action): 클릭된 액션 버튼의 정보를 담은 객체
                           (name, value, label 등의 속성 포함)
    """
    # 현재 설정값 가져오기 (없으면 False)
    current = cl.user_session.get("reset_context", False)
    # 반대값으로 설정 (True -> False, False -> True)
    cl.user_session.set("reset_context", not current)
    # 변경된 상태 메시지 표시
    status = "활성화" if not current else "비활성화"
    await cl.Message(content=f"🔄 컨텍스트 리셋이 **{status}** 되었습니다.").send()

@cl.action_callback("toggle_streaming")
async def toggle_streaming(action: cl.Action):
    """
    스트리밍 모드 설정을 토글하는 액션 콜백입니다.

    '📡 스트리밍 토글' 버튼을 클릭하면 호출됩니다.
    현재 설정값의 반대값으로 변경합니다.

    Args:
        action (cl.Action): 클릭된 액션 버튼 정보
    """
    current = cl.user_session.get("use_streaming", True)
    cl.user_session.set("use_streaming", not current)
    status = "활성화" if not current else "비활성화"
    await cl.Message(content=f"📡 스트리밍 모드가 **{status}** 되었습니다.").send()

@cl.action_callback("reset_session")
async def reset_session(action: cl.Action):
    """
    현재 세션을 초기화하는 액션 콜백입니다.

    '🗑️ 세션 초기화' 버튼을 클릭하면 호출됩니다.
    API 서버에 세션 리셋 요청을 보내고 새로운 세션 ID를 생성합니다.

    동작:
    1. API 서버의 /reset/{session_id} 엔드포인트 호출
    2. 새로운 세션 ID 생성
    3. 클라이언트 세션 스토리지 업데이트

    Args:
        action (cl.Action): 클릭된 액션 버튼 정보
    """
    session_id = cl.user_session.get("session_id")
    try:
        # API 서버에 세션 리셋 요청
        # 서버 측에서 해당 세션의 대화 히스토리가 삭제됨
        requests.post(f"{API_BASE_URL}/reset/{session_id}", timeout=5)

        # 새로운 세션 ID 생성 및 저장
        new_session_id = str(uuid.uuid4())[:8]
        cl.user_session.set("session_id", new_session_id)

        await cl.Message(
            content=f"🗑️ 세션이 초기화되었습니다.\n새 세션 ID: `{new_session_id}`"
        ).send()
    except Exception as e:
        await cl.Message(content=f"❌ 세션 초기화 실패: {str(e)}").send()

@cl.action_callback("show_settings")
async def show_settings(action: cl.Action):
    """
    현재 설정을 표시하고 설정 변경 버튼들을 제공하는 액션 콜백입니다.

    '⚙️ 설정' 버튼이나 '/settings' 명령어를 통해 호출됩니다.
    현재 세션의 모든 설정값을 표시하고, 각 설정을 변경할 수 있는
    인라인 액션 버튼들을 함께 제공합니다.

    Args:
        action (cl.Action): 클릭된 액션 버튼 정보 (명령어로 호출 시 None)
    """
    # 현재 설정값들 조회
    session_id = cl.user_session.get("session_id")
    reset_context = cl.user_session.get("reset_context", False)
    use_streaming = cl.user_session.get("use_streaming", True)

    # 설정 정보 메시지와 함께 액션 버튼들 표시
    await cl.Message(
        content=f"⚙️ **현재 설정**\n\n"
                f"- 세션 ID: `{session_id}`\n"
                f"- 컨텍스트 리셋: {'✅ 활성화' if reset_context else '❌ 비활성화'}\n"
                f"- 스트리밍 모드: {'✅ 활성화' if use_streaming else '❌ 비활성화'}",
        # actions 파라미터에 버튼 목록을 전달하면 메시지 하단에 버튼이 렌더링됨
        actions=[
            # name: action_callback 데코레이터의 이름과 일치해야 함
            # value: 콜백 함수에 전달되는 값 (현재는 사용하지 않음)
            # label: 버튼에 표시되는 텍스트
            cl.Action(name="toggle_reset_context", payload={"action": "toggle_reset"}, label="🔄 컨텍스트 리셋 토글"),
            cl.Action(name="toggle_streaming", payload={"action": "toggle_stream"}, label="📡 스트리밍 토글"),
            cl.Action(name="reset_session", payload={"action": "reset"}, label="🗑️ 세션 초기화"),
        ]
    ).send()

# -----------------------------------------------------------------------------
# 스트리밍 응답 처리 함수
# -----------------------------------------------------------------------------
async def stream_response(query: str, session_id: str, reset: bool, msg: cl.Message) -> dict:
    """
    Server-Sent Events (SSE) 방식으로 스트리밍 응답을 처리합니다.

    API 서버에 스트리밍 요청을 보내고, 응답을 토큰 단위로 받아서
    실시간으로 화면에 표시합니다. ChatGPT처럼 글자가 하나씩 나타나는
    효과를 구현합니다.

    SSE 프로토콜 형식:
        data: {"type": "metadata", "cypher": "...", "context": [...]}
        data: {"type": "token", "content": "응답 "}
        data: {"type": "token", "content": "텍스트"}
        data: {"type": "done"}

    Args:
        query (str): 사용자의 질문 텍스트
        session_id (str): 현재 세션 식별자
        reset (bool): 컨텍스트 리셋 여부
        msg (cl.Message): 응답을 표시할 Chainlit 메시지 객체
                         이 객체에 stream_token()을 호출하여 실시간 업데이트

    Returns:
        dict: 응답 결과를 담은 딕셔너리
              - answer: 전체 응답 텍스트
              - cypher: 생성된 Cypher 쿼리 (있는 경우)
              - context: 검색된 컨텍스트 데이터 (있는 경우)

    Notes:
        - requests.post()의 stream=True 옵션으로 응답을 청크 단위로 수신
        - iter_lines()로 SSE 이벤트를 라인별로 처리
        - msg.stream_token()으로 토큰을 실시간 표시
    """
    # 메타데이터 저장용 딕셔너리 (cypher, context 등)
    metadata = {}
    # 전체 응답 텍스트를 누적 저장
    full_response = ""

    try:
        # ---------------------------------------------------------------------
        # API 서버에 스트리밍 요청 전송
        # ---------------------------------------------------------------------
        response = requests.post(
            f"{API_BASE_URL}/query",
            json={
                "query": query,           # 사용자 질문
                "session_id": session_id, # 세션 ID
                "reset_context": reset,   # 컨텍스트 리셋 여부
                "stream": True            # 스트리밍 모드 활성화
            },
            stream=True,  # 응답을 청크 단위로 수신 (SSE용)
            timeout=60    # 60초 타임아웃 (LLM 응답은 시간이 걸릴 수 있음)
        )

        # ---------------------------------------------------------------------
        # SSE 이벤트 스트림 처리
        # ---------------------------------------------------------------------
        # iter_lines()는 응답을 라인 단위로 이터레이트
        for line in response.iter_lines():
            if line:  # 빈 라인 무시 (SSE에서 이벤트 구분자로 사용됨)
                # 바이트를 문자열로 디코딩
                line_str = line.decode('utf-8')

                # SSE 형식: "data: {json}" - 'data: ' 접두사 확인
                if line_str.startswith('data: '):
                    try:
                        # 'data: ' 이후의 JSON 파싱 (6글자 이후)
                        data = json.loads(line_str[6:])

                        # 이벤트 타입별 처리
                        if data.get('type') == 'metadata':
                            # 메타데이터 이벤트: Cypher 쿼리와 컨텍스트 정보
                            # 응답 텍스트 전에 먼저 전송됨
                            metadata['cypher'] = data.get('cypher', '')
                            metadata['context'] = data.get('context', [])

                        elif data.get('type') == 'token':
                            # 토큰 이벤트: 응답 텍스트의 일부
                            # LLM이 생성한 텍스트를 토큰 단위로 전송
                            token = data.get('content', '')
                            full_response += token  # 전체 응답에 누적
                            await msg.stream_token(token)  # 화면에 실시간 표시

                        elif data.get('type') == 'done':
                            # 완료 이벤트: 스트리밍 종료 (토큰 사용량 포함)
                            if 'token_usage' in data:
                                metadata['token_usage'] = data['token_usage']
                            break

                        elif data.get('type') == 'error':
                            # 에러 이벤트: 서버측 오류 발생
                            error_msg = data.get('message', 'Unknown error')
                            full_response += f"\n\n❌ 오류: {error_msg}"
                            await msg.stream_token(f"\n\n❌ 오류: {error_msg}")
                            break

                    except json.JSONDecodeError:
                        # JSON 파싱 실패 시 해당 라인 무시하고 계속 진행
                        continue

    except requests.exceptions.ConnectionError:
        # 네트워크 연결 오류
        full_response = "❌ API 서버에 연결할 수 없습니다."
        await msg.stream_token(full_response)
    except Exception as e:
        # 기타 예외 (타임아웃 등)
        full_response = f"❌ 오류가 발생했습니다: {str(e)}"
        await msg.stream_token(full_response)

    # 전체 응답을 메타데이터에 추가하여 반환
    metadata['answer'] = full_response
    return metadata

# -----------------------------------------------------------------------------
# 일반 (Non-Streaming) 응답 처리 함수
# -----------------------------------------------------------------------------
async def get_response(query: str, session_id: str, reset: bool) -> dict:
    """
    일반(non-streaming) 방식으로 API 응답을 처리합니다.

    스트리밍 모드가 비활성화된 경우 사용됩니다.
    전체 응답이 생성될 때까지 기다린 후 한 번에 반환합니다.

    Args:
        query (str): 사용자의 질문 텍스트
        session_id (str): 현재 세션 식별자
        reset (bool): 컨텍스트 리셋 여부

    Returns:
        dict: API 응답 데이터
              - answer: 응답 텍스트
              - cypher: 생성된 Cypher 쿼리
              - context: 검색된 컨텍스트 데이터
              오류 발생 시 answer에 오류 메시지 포함

    Notes:
        - 스트리밍보다 간단하지만 응답 완료까지 사용자가 기다려야 함
        - 네트워크 상태가 불안정한 경우 더 안정적일 수 있음
    """
    try:
        # API 서버에 쿼리 요청 전송
        response = requests.post(
            f"{API_BASE_URL}/query",
            json={
                "query": query,
                "session_id": session_id,
                "reset_context": reset,
                "stream": False  # 스트리밍 비활성화
            },
            timeout=60  # LLM 응답 대기를 위한 충분한 타임아웃
        )

        if response.status_code == 200:
            # 성공: JSON 응답 반환
            return response.json()
        else:
            # HTTP 오류 (4xx, 5xx)
            return {
                "answer": f"❌ 오류: HTTP {response.status_code}",
                "cypher": "",
                "context": []
            }

    except requests.exceptions.ConnectionError:
        # 서버 연결 불가
        return {
            "answer": "❌ API 서버에 연결할 수 없습니다.",
            "cypher": "",
            "context": []
        }
    except Exception as e:
        # 기타 예외
        return {
            "answer": f"❌ 오류가 발생했습니다: {str(e)}",
            "cypher": "",
            "context": []
        }

# -----------------------------------------------------------------------------
# 메시지 수신 이벤트 핸들러
# -----------------------------------------------------------------------------
@cl.on_message
async def on_message(message: cl.Message):
    """
    사용자가 메시지를 전송할 때 호출되는 메인 이벤트 핸들러입니다.

    이 함수는 채팅 애플리케이션의 핵심 로직을 담당합니다:
    1. 사용자 입력을 받아 명령어인지 일반 질문인지 구분
    2. 명령어인 경우 해당 기능 실행
    3. 일반 질문인 경우 API 서버에 전달하고 응답 표시
    4. 메타데이터(Cypher, Context)가 있으면 추가 표시

    Args:
        message (cl.Message): 사용자가 전송한 메시지 객체
                             content 속성에 메시지 텍스트 포함

    지원 명령어:
        /settings, /설정, 설정 - 현재 설정 보기
        /reset, /초기화, 초기화 - 세션 초기화
        /help, /도움말, 도움말 - 도움말 보기
    """
    # 메시지 텍스트에서 앞뒤 공백 제거
    query = message.content.strip()

    # -------------------------------------------------------------------------
    # 명령어 처리
    # -------------------------------------------------------------------------
    # 설정 보기 명령어
    if query.lower() in ["/settings", "/설정", "설정"]:
        await show_settings(None)  # action=None으로 호출 (명령어 통한 호출)
        return

    # 세션 초기화 명령어
    if query.lower() in ["/reset", "/초기화", "초기화"]:
        await reset_session(None)
        return

    # 도움말 명령어
    if query.lower() in ["/help", "/도움말", "도움말"]:
        await cl.Message(
            content="📖 **사용 가능한 명령어**\n\n"
                    "- `/settings` 또는 `설정` - 현재 설정 보기\n"
                    "- `/reset` 또는 `초기화` - 세션 초기화\n"
                    "- `/help` 또는 `도움말` - 도움말 보기\n\n"
                    "영화에 대해 자유롭게 질문하세요!"
        ).send()
        return

    # -------------------------------------------------------------------------
    # 일반 질문 처리
    # -------------------------------------------------------------------------
    # 세션 정보 및 설정값 조회
    session_id = cl.user_session.get("session_id")
    reset_context = cl.user_session.get("reset_context", False)
    use_streaming = cl.user_session.get("use_streaming", True)

    # 빈 응답 메시지 객체 생성 및 전송
    # 스트리밍 모드에서는 이 메시지에 토큰이 점진적으로 추가됨
    msg = cl.Message(content="")
    await msg.send()  # 빈 메시지를 먼저 전송 (스트리밍 준비)

    # -------------------------------------------------------------------------
    # API 호출 및 응답 처리
    # -------------------------------------------------------------------------
    if use_streaming:
        # 스트리밍 모드: 토큰 단위로 실시간 표시
        result = await stream_response(query, session_id, reset_context, msg)
    else:
        # 일반 모드: 전체 응답을 한 번에 표시
        result = await get_response(query, session_id, reset_context)
        msg.content = result.get("answer", "")
        await msg.update()  # 메시지 내용 업데이트

    # -------------------------------------------------------------------------
    # 메타데이터 표시 (Cypher 쿼리, Context, Token Usage)
    # -------------------------------------------------------------------------
    cypher = result.get("cypher", "")
    context = result.get("context", [])
    token_usage = result.get("token_usage")

    # Cypher 쿼리, Context, 또는 Token Usage가 있는 경우 상세 정보 표시
    if cypher or context or token_usage:
        # Chainlit 2.x에서는 마크다운으로 직접 표시
        details_content = "🔍 **상세 정보**\n\n"

        if cypher:
            details_content += "**Cypher Query:**\n```cypher\n" + cypher + "\n```\n\n"

        if context and len(context) > 0:
            # Context 데이터를 JSON 형식으로 포맷팅 (상위 5개만)
            context_str = json.dumps(context[:5], indent=2, ensure_ascii=False)
            details_content += "**Context (Top 5):**\n```json\n" + context_str + "\n```\n\n"

        if token_usage:
            total = token_usage.get("total_tokens", 0)
            prompt = token_usage.get("prompt_tokens", 0)
            completion = token_usage.get("completion_tokens", 0)
            cost = token_usage.get("total_cost", 0.0)
            details_content += (
                f"**Token Usage:**\n"
                f"| Prompt | Completion | Total | Cost |\n"
                f"|--------|------------|-------|------|\n"
                f"| {prompt:,} | {completion:,} | {total:,} | ${cost:.6f} |"
            )

        await cl.Message(
            content=details_content,
            actions=[
                cl.Action(name="show_settings", payload={"action": "settings"}, label="⚙️ 설정"),
            ]
        ).send()

# -----------------------------------------------------------------------------
# 세션 종료 이벤트 핸들러
# -----------------------------------------------------------------------------
@cl.on_chat_end
async def on_chat_end():
    """
    채팅 세션이 종료될 때 호출되는 Chainlit 이벤트 핸들러입니다.

    사용자가 브라우저 탭을 닫거나 세션이 타임아웃될 때 호출됩니다.
    서버 측의 세션 데이터를 정리하기 위해 리셋 요청을 보냅니다.

    Notes:
        - 예외가 발생해도 무시 (세션 종료 시점이므로 복구 불필요)
        - 서버 측 메모리 누수 방지를 위한 클린업 작업
    """
    session_id = cl.user_session.get("session_id")
    if session_id:
        try:
            # API 서버에 세션 정리 요청
            # 서버 측의 대화 히스토리 메모리를 해제
            requests.post(f"{API_BASE_URL}/reset/{session_id}", timeout=5)
        except:
            # 세션 종료 시점이므로 오류 무시
            # 네트워크 오류나 서버 다운 등의 상황에서도 정상 종료
            pass
