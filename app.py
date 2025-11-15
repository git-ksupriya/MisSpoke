from __future__ import annotations

import logging
import os
import uuid
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import threading
import requests
from dotenv import load_dotenv

try:  # Optional Azure Speech SDK; degrade gracefully if not installed
    import azure.cognitiveservices.speech as speechsdk  # type: ignore[attr-defined]
except Exception:  # pragma: no cover - optional dependency
    speechsdk = None  # type: ignore[assignment]

try:  # Optional Agora token builder; we fall back gracefully if missing
    from agora_token_builder import RtcTokenBuilder  # type: ignore[import]
except Exception:  # pragma: no cover - optional dependency
    RtcTokenBuilder = None  # type: ignore[assignment]

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# Load environment variables from a local .env file if present.
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

STATIC_DIR = BASE_DIR / "static"

logger = logging.getLogger("mis-spoke")
logging.basicConfig(level=logging.INFO)

app = FastAPI(
    title="MisSpoke",
    description=(
        "MisSpoke: dark-mode conversational language tutor using Agora Conversational AI "
        "and video RTC."
    ),
)


@app.on_event("startup")
async def startup_validation() -> None:
    """Log configuration problems early instead of failing at first request."""

    required_vars = ["AGORA_APP_ID"]
    missing = [var for var in required_vars if not os.getenv(var)]
    if missing:
        logger.warning("Missing env vars: %s", ", ".join(missing))
    else:
        logger.info("MisSpoke startup: required env vars present.")
    
    # Log API configuration status
    if AGORA_CONVAI_CHAT_URL:
        logger.info("✓ Agora ConvAI URL configured: %s", AGORA_CONVAI_CHAT_URL)
        if AGORA_CONVAI_API_KEY:
            logger.info("✓ Using API Key authentication")
        elif AGORA_CREDENTIALS:
            logger.info("✓ Using Basic authentication")
        else:
            logger.warning("⚠ ConvAI URL set but no auth credentials found")
    elif GROQ_API_KEY:
        logger.info("✓ Groq API Key configured, will use Groq as fallback")
    else:
        logger.warning("⚠ No AI backend configured, using stub responses")

# Allow browser clients (and a future frontend) to talk to this API.
ALLOWED_ORIGINS_RAW = os.getenv("ALLOWED_ORIGINS", "*")
if ALLOWED_ORIGINS_RAW == "*":
    allowed_origins: List[str] = ["*"]
else:
    allowed_origins = [o.strip() for o in ALLOWED_ORIGINS_RAW.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve the single-page app from / and /static.
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", response_class=FileResponse)
async def root() -> FileResponse:
    """Serve the main web UI.

    The UI is a single-page app in static/index.html that drives the different
    flows: landing, tutor, writing practice, progress, and session summary.
    """

    index_file = STATIC_DIR / "index.html"
    if not index_file.exists():
        raise HTTPException(status_code=500, detail="Frontend not built yet (missing index.html)")

    return FileResponse(index_file)


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


ALLOWED_LANGUAGES = {
    "English",
    "Spanish",
    "French",
    "Japanese",
    "Korean",
    "Mandarin",
}
MAX_MESSAGE_LENGTH = 2000


class SessionStartRequest(BaseModel):
    user_id: str
    familiar_language: str
    target_language: str


class SessionState(BaseModel):
    user_id: str
    familiar_language: str
    target_language: str
    turns: int = 0
    fluency: float = 0.0  # 0.0–1.0


class TutorMessage(BaseModel):
    user_id: str
    familiar_language: str
    target_language: str
    message: str


class TutorReply(BaseModel):
    reply: str
    trace_id: str


class VideoTokenRequest(BaseModel):
    channel: str
    uid: str


class VideoTokenResponse(BaseModel):
    app_id: str
    channel: str
    token: str


class ProgressSnapshot(BaseModel):
    speaking: float
    listening: float
    writing: float
    fluency: float


class Profile(BaseModel):
    user_id: str
    description: str
    familiar_language: str
    target_language: str
    turns: int
    fluency: float


class WritingScoreRequest(BaseModel):
    user_id: str
    target_language: str
    text: str


class WritingScoreResponse(BaseModel):
    accuracy: float
    feedback: str


class SessionSummary(BaseModel):
    message: str


class ConvAIJoinRequest(BaseModel):
    channel: str
    user_uid: str


class ConvAIJoinResponse(BaseModel):
    status: str
    details: Optional[Dict[str, Any]] = None


# ---------------------------------------------------------------------------
# Configuration helpers (Agora + ConvAI)
# ---------------------------------------------------------------------------


AGORA_APP_ID = os.getenv("AGORA_APP_ID")
AGORA_APP_CERTIFICATE = os.getenv("AGORA_APP_CERTIFICATE")
AGORA_AGENT_ID = os.getenv("AGORA_AGENT_ID")  # Optional: ConvAI agent identifier
AGORA_CHANNEL = os.getenv("AGORA_CHANNEL")
AGORA_TOKEN_SERVER_URL = os.getenv("AGORA_TOKEN_SERVER_URL")
AGORA_RTC_TOKEN_EXPIRE_SECONDS = int(os.getenv("AGORA_RTC_TOKEN_EXPIRE_SECONDS", "3600"))

# The Conversational AI endpoint should be provided as a full URL in env.
# Example: https://example.com/agora/convai/chat
AGORA_CONVAI_CHAT_URL = os.getenv("AGORA_CONVAI_CHAT_URL")
AGORA_CONVAI_API_KEY = os.getenv("AGORA_CONVAI_API_KEY")
AGORA_CREDENTIALS = os.getenv("AGORA_CREDENTIALS")  # e.g. "Basic base64(customer_id:secret)"

# Groq LLM configuration (used as a fallback/general LLM backend)
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_API_URL = os.getenv("GROQ_API_URL", "https://api.groq.com/openai/v1/chat/completions")
# Default to the same model you are already using in your working Groq integration.
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")

# Azure Speech configuration (for server-side TTS)
AZURE_SPEECH_KEY = os.getenv("AZURE_SPEECH_KEY")
AZURE_SPEECH_REGION = os.getenv("AZURE_SPEECH_REGION")
AZURE_SPEECH_VOICE = os.getenv("AZURE_SPEECH_VOICE", "en-US-AndrewMultilingualNeural")


# In-memory session state for prototyping purposes only.
SESSIONS: Dict[str, SessionState] = {}

# Simple in-memory rate limiting: user_id -> [timestamps]
RATE_LIMIT_WINDOW_SECONDS = int(os.getenv("RATE_LIMIT_WINDOW_SECONDS", "10"))
RATE_LIMIT_MAX_REQUESTS = int(os.getenv("RATE_LIMIT_MAX_REQUESTS", "10"))
USER_REQUEST_TIMESTAMPS: Dict[str, List[float]] = {}


def _validate_language(label: str, value: str) -> None:
    if value not in ALLOWED_LANGUAGES:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid {label} language: {value}",
        )


def _rate_limit(user_id: str) -> None:
    """Very simple per-user rate limiting for tutor messages."""

    import time

    now = time.time()
    timestamps = USER_REQUEST_TIMESTAMPS.get(user_id, [])
    cutoff = now - RATE_LIMIT_WINDOW_SECONDS
    timestamps = [t for t in timestamps if t >= cutoff]
    if len(timestamps) >= RATE_LIMIT_MAX_REQUESTS:
        raise HTTPException(status_code=429, detail="Too many requests. Please slow down.")
    timestamps.append(now)
    USER_REQUEST_TIMESTAMPS[user_id] = timestamps


def _get_or_create_session(user_id: str, familiar_language: str, target_language: str) -> SessionState:
    existing = SESSIONS.get(user_id)
    if existing:
        # Make sure languages stay up to date if user changes them.
        existing.familiar_language = familiar_language
        existing.target_language = target_language
        SESSIONS[user_id] = existing
        return existing

    state = SessionState(
        user_id=user_id,
        familiar_language=familiar_language,
        target_language=target_language,
        turns=0,
        fluency=0.0,
    )
    SESSIONS[user_id] = state
    return state


def _update_fluency(state: SessionState, last_message: str) -> SessionState:
    """Heuristic for fluency progression.

    Every tutor turn nudges fluency higher, capped at 1.0. The increment
    depends on current fluency and a rough proxy for effort (message length).
    This is intentionally simple and should be replaced with a real assessment
    model when available.
    """

    state.turns += 1

    # Use message length as a crude proxy for effort.
    length = len((last_message or "").strip())
    # Base increment plus a small bonus for longer messages.
    base = 0.05
    bonus = min(0.15, length / 80.0)  # cap bonus so we never jump too far.
    increment = (base + bonus) * (1.0 - state.fluency)

    state.fluency = min(1.0, state.fluency + increment)
    SESSIONS[state.user_id] = state
    return state


def _language_mix(fluency: float) -> Tuple[int, int]:
    """Return (familiar_pct, target_pct) based on fluency.

    - 0.00–0.25  -> 90 / 10
    - 0.25–0.50 -> 80 / 20
    - 0.50–0.75 -> 70 / 30
    - 0.75+     -> 50 / 50
    """

    if fluency < 0.25:
        return (90, 10)
    if fluency < 0.5:
        return (80, 20)
    if fluency < 0.75:
        return (70, 30)
    return (50, 50)


def _strip_emoji(text: str) -> str:
    """Remove common emoji ranges so they are not sent to Azure TTS.

    This keeps spoken output cleaner while preserving the on-screen text.
    """

    try:
        import re

        return re.sub(r"[\U0001F300-\U0001FAFF\u2600-\u26FF\u2700-\u27BF]", "", text)
    except Exception:
        return text


def _speak_azure(text: str) -> None:
    """Speak text via Azure Speech on the server machine.

    This uses the same pattern as your standalone Groq+Azure script. It is
    best-effort and will log warnings instead of failing the request if Azure
    is misconfigured or the SDK is unavailable.
    """

    if not text:
        return
    if not (AZURE_SPEECH_KEY and AZURE_SPEECH_REGION and speechsdk):
        return

    cleaned = _strip_emoji(text).strip()
    if not cleaned:
        return

    try:
        speech_config = speechsdk.SpeechConfig(
            subscription=AZURE_SPEECH_KEY,
            region=AZURE_SPEECH_REGION,
        )
        speech_config.speech_synthesis_voice_name = AZURE_SPEECH_VOICE
        audio_config = speechsdk.audio.AudioOutputConfig(use_default_speaker=True)
        synthesizer = speechsdk.SpeechSynthesizer(
            speech_config=speech_config,
            audio_config=audio_config,
        )
        result = synthesizer.speak_text_async(cleaned).get()
        if result.reason != speechsdk.ResultReason.SynthesizingAudioCompleted:
            logger.warning("Azure TTS did not complete successfully: %s", result.reason)
    except Exception as exc:  # pragma: no cover - optional path
        logger.warning("Azure TTS exception: %s", exc)


def _call_agora_convai(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Call Agora Conversational AI or Groq LLM, falling back to a local stub.

    Priority:
    1. If an Agora ConvAI REST endpoint + credentials are configured, call that.
    2. Else if GROQ_API_KEY is configured, call Groq's chat completions API.
    3. Else, fall back to an echo stub.
    """

    message = payload.get("message", "")
    familiar_language = payload.get("familiar_language")
    target_language = payload.get("target_language")
    fluency = payload.get("fluency", 0.0)
    mix = payload.get("language_mix") or {}
    familiar_pct = mix.get("familiar_pct", 90)
    target_pct = mix.get("target_pct", 10)

    # 1) Try Agora ConvAI REST gateway if configured and not pointing at a /join endpoint
    use_agora_convai = bool(
        AGORA_CONVAI_CHAT_URL
        and (AGORA_CONVAI_API_KEY or AGORA_CREDENTIALS)
        and "/join" not in AGORA_CONVAI_CHAT_URL
    )

    if use_agora_convai:
        headers = {"Content-Type": "application/json"}
        if AGORA_CONVAI_API_KEY:
            headers["Authorization"] = f"Bearer {AGORA_CONVAI_API_KEY}"
        elif AGORA_CREDENTIALS:
            headers["Authorization"] = AGORA_CREDENTIALS

        try:
            logger.info("Calling Agora ConvAI at %s", AGORA_CONVAI_CHAT_URL)
            response = requests.post(
                AGORA_CONVAI_CHAT_URL,
                json=payload,
                headers=headers,
                timeout=15,
            )
            logger.info("Agora ConvAI response status: %d", response.status_code)
            
            response.raise_for_status()
            data: Dict[str, Any] = response.json()
            logger.info("Agora ConvAI response data keys: %s", list(data.keys()))
            
            reply_text = (
                data.get("reply")
                or data.get("text")
                or data.get("message")
                or data.get("response")
                or str(data)
            )
            trace_id = data.get("trace_id") or str(uuid.uuid4())
            logger.info("✓ Successfully got reply from Agora ConvAI")
            return {"reply": reply_text, "trace_id": trace_id}
            
        except requests.RequestException as e:
            logger.error("✗ Agora ConvAI call failed: %s - %s", type(e).__name__, str(e))
            logger.info("Falling back to Groq or stub")
        except (ValueError, KeyError) as e:
            logger.error("✗ Failed to parse Agora ConvAI response: %s", str(e))
            logger.info("Falling back to Groq or stub")

    # 2) Try Groq LLM if configured
    if GROQ_API_KEY:
        system_prompt = (
            f"You are MisSpoke, a friendly, gentle language tutor helping the learner practice {target_language}. "
            f"The learner is familiar with {familiar_language}. Their current fluency in {target_language} "
            f"is approximately {fluency * 100:.0f}%. "
            f"Mix languages in your response: use about {familiar_pct}% {familiar_language} and {target_pct}% {target_language}. "
            f"Start with more {familiar_language} for beginners, and gradually increase {target_language} as they improve. "
            f"Respond in plain text only (no markdown, bullet lists, code fences, or numbered sections). "
            f"Keep answers short and readable: at most 3 short paragraphs, each 1–2 sentences. "
            f"Be encouraging, correct mistakes briefly, and end with a simple follow-up question in the target language."
        )

        user_prompt = f"Learner message: {message}"

        try:
            logger.info("Calling Groq API as fallback (model=%s)", GROQ_MODEL)
            response = requests.post(
                GROQ_API_URL,
                headers={
                    "Authorization": f"Bearer {GROQ_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": GROQ_MODEL,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    "temperature": 0.7,
                    "max_tokens": 500,
                    "stream": False,
                },
                timeout=20,
            )
            logger.info("Groq API response status: %d", response.status_code)
            
            response.raise_for_status()
            data: Dict[str, Any] = response.json()
            choices: List[Dict[str, Any]] = data.get("choices") or []
            
            if choices:
                reply_content = choices[0].get("message", {}).get("content")
                if reply_content:
                    logger.info("✓ Successfully got reply from Groq")
                    # Speak on the server using Azure Speech in the background so
                    # the HTTP response (and on-screen text) is not delayed.
                    threading.Thread(target=_speak_azure, args=(reply_content,), daemon=True).start()
                    return {"reply": reply_content, "trace_id": str(uuid.uuid4())}
            
            logger.warning("Groq response had no content, using stub")
            
        except requests.RequestException as e:
            logger.error("✗ Groq LLM call failed: %s - %s", type(e).__name__, str(e))
        except (ValueError, KeyError) as e:
            logger.error("✗ Failed to parse Groq response: %s", str(e))

    # 3) Final fallback: local echo stub with helpful message
    logger.warning("⚠ Using stub response - no AI backend is working")
    
    stub_replies = {
        "hello": f"Hello! I'm your {target_language} tutor. (Using stub - configure GROQ_API_KEY or AGORA_CONVAI_CHAT_URL for real AI responses)",
        "hi": f"Hi there! Ready to practice {target_language}? (Stub mode)",
        "default": f"I understand you said: '{message}'. (Stub mode - configure an AI backend for real tutoring)"
    }
    
    message_lower = message.lower().strip()
    reply = stub_replies.get(message_lower, stub_replies["default"])
    
    return {
        "reply": reply,
        "trace_id": f"stub-{uuid.uuid4()}",
    }


def _fetch_agora_video_token(channel: str, uid: str) -> VideoTokenResponse:
    """Obtain an Agora RTC token.

    Priority:
    1. If `AGORA_TOKEN_SERVER_URL` is configured, call that external token server.
    2. Else if `AGORA_APP_CERTIFICATE` and `RtcTokenBuilder` are available, generate
       an RTC token locally using the Agora token builder library.

    If neither path is available or token generation fails, this raises an HTTP 5xx
    instead of returning a dummy token so failures are visible.
    """

    if not AGORA_APP_ID:
        raise HTTPException(status_code=500, detail="AGORA_APP_ID is not configured")

    # 1) External token server (if provided)
    if AGORA_TOKEN_SERVER_URL:
        try:
            response = requests.post(
                AGORA_TOKEN_SERVER_URL,
                json={"channel": channel, "uid": uid},
                timeout=10,
            )
            response.raise_for_status()
        except requests.RequestException as exc:  # pragma: no cover - network error path
            raise HTTPException(status_code=502, detail=f"Token server request failed: {exc}") from exc

        data: Dict[str, Any] = response.json()
        token: Optional[str] = data.get("token")

        if not token:
            raise HTTPException(status_code=500, detail="Token server did not return a 'token' field")

        logger.info("Using RTC token from external token server for channel=%s uid=%s", channel, uid)
        return VideoTokenResponse(app_id=AGORA_APP_ID, channel=channel, token=token)

    # 2) Local token generation using Agora app certificate (no external server)
    if AGORA_APP_CERTIFICATE and RtcTokenBuilder is not None:
        try:
            import time

            try:
                uid_int = int(uid)
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=f"RTC uid must be numeric, got '{uid}'") from exc

            role_publisher = 1  # Agora Role_Publisher
            expire_ts = int(time.time()) + AGORA_RTC_TOKEN_EXPIRE_SECONDS
            # Most versions of agora-token-builder expose buildTokenWithUid for numeric UIDs.
            token = RtcTokenBuilder.buildTokenWithUid(
                AGORA_APP_ID,
                AGORA_APP_CERTIFICATE,
                channel,
                uid_int,
                role_publisher,
                expire_ts,
            )
            logger.info("Using locally generated RTC token for channel=%s uid=%s", channel, uid_int)
            return VideoTokenResponse(app_id=AGORA_APP_ID, channel=channel, token=token)
        except HTTPException:
            raise
        except Exception as exc:  # pragma: no cover - optional path
            logger.error("Agora local token generation failed: %s", exc)
            raise HTTPException(status_code=500, detail=f"Local RTC token generation failed: {exc}") from exc

    # 3) No way to generate a token.
    raise HTTPException(status_code=500, detail="No RTC token mechanism configured (AGORA_TOKEN_SERVER_URL or AGORA_APP_CERTIFICATE + agora-token-builder)")


def _convai_join_rtc(channel: str, user_uid: str) -> Dict[str, Any]:
    """Ask Agora Conversational AI agent to join the same RTC channel as the user.

    This mirrors your working ConvAI join script: the agent uses a numeric RTC uid
    (0), and the join payload configures Groq as the LLM and Azure as TTS.
    """

    if not AGORA_CONVAI_CHAT_URL or "/join" not in AGORA_CONVAI_CHAT_URL:
        raise HTTPException(status_code=500, detail="AGORA_CONVAI_CHAT_URL for /join is not configured")
    if not AGORA_CREDENTIALS:
        raise HTTPException(status_code=500, detail="AGORA_CREDENTIALS (Basic ...) is required for ConvAI join")

    # Generate an RTC token for the ConvAI agent to join this channel with uid 0.
    agent_rtc_uid = "0"
    agent_token = _fetch_agora_video_token(channel=channel, uid=agent_rtc_uid).token

    # LLM + TTS config for ConvAI agent, matching your example script.
    llm_config: Dict[str, Any] = {
        "url": GROQ_API_URL,
        "api_key": GROQ_API_KEY,
        "system_messages": [
            {
                "role": "system",
                "content": (
                    "You are MisSpoke, a gentle, encouraging language tutor. "
                    "You practice conversational language with the user in real time."
                ),
            }
        ],
        "greeting_message": "Hello, how can I help you today?",
        "failure_message": "Sorry, I don't know how to answer this question.",
        "max_history": 10,
        "params": {
            "model": GROQ_MODEL,
            "stream": True,
        },
    }

    tts_config: Dict[str, Any] = {
        "vendor": "microsoft",
        "params": {
            "key": AZURE_SPEECH_KEY,
            "region": AZURE_SPEECH_REGION,
            "voice_name": AZURE_SPEECH_VOICE,
            "speed": 1.0,
            "volume": 70,
            "sample_rate": 24000,
        },
    }

    asr_config: Dict[str, Any] = {
        "language": "en-US",
    }

    join_payload: Dict[str, Any] = {
        "name": "MisSpoke",
        "properties": {
            "channel": channel,
            "token": agent_token,
            "agent_rtc_uid": agent_rtc_uid,
            "remote_rtc_uids": ["*"],
            "enable_string_uid": False,
            "idle_timeout": 120,
            "llm": llm_config,
            "asr": asr_config,
            "tts": tts_config,
        },
    }

    headers = {
        "Content-Type": "application/json",
        "Authorization": AGORA_CREDENTIALS,
    }

    try:
        logger.info("Calling Agora ConvAI /join at %s for channel=%s", AGORA_CONVAI_CHAT_URL, channel)
        response = requests.post(
            AGORA_CONVAI_CHAT_URL,
            json=join_payload,
            headers=headers,
            timeout=15,
        )
        logger.info("Agora ConvAI /join response status: %d", response.status_code)

        # 409 Conflict is commonly returned when an agent is already joined on
        # this project/channel. Treat that as a non-fatal "already joined".
        if response.status_code == 409:
            body_text = response.text
            logger.warning("ConvAI /join returned 409 (already joined?) for channel %s: %s", channel, body_text)
            return {"status": "already_joined", "raw": body_text}

        response.raise_for_status()
        data: Dict[str, Any] = response.json()
        logger.info("✓ ConvAI agent join accepted for channel %s", channel)
        return data
    except requests.RequestException as exc:
        # Log full body when available for easier debugging.
        try:
            body_text = response.text  # type: ignore[name-defined]
        except Exception:
            body_text = "<no body>"
        logger.error("✗ ConvAI /join call failed: %s - %s; body=%s", type(exc).__name__, str(exc), body_text)
        raise HTTPException(status_code=502, detail=f"ConvAI join failed: {exc}") from exc


# ---------------------------------------------------------------------------
# REST API endpoints
# ---------------------------------------------------------------------------


@app.post("/api/session/start", response_model=SessionState)
async def start_session(body: SessionStartRequest) -> SessionState:
    """Initialize or resume a MisSpoke tutoring session for a user.

    This sets up in-memory tracking of familiar/target languages and fluency.
    """

    # Basic input validation
    _validate_language("familiar", body.familiar_language)
    _validate_language("target", body.target_language)

    state = _get_or_create_session(
        user_id=body.user_id,
        familiar_language=body.familiar_language,
        target_language=body.target_language,
    )
    logger.info(
        "Session started: user_id=%s familiar=%s target=%s",
        body.user_id,
        body.familiar_language,
        body.target_language,
    )
    return state


@app.post("/api/tutor/message", response_model=TutorReply)
async def tutor_message(msg: TutorMessage) -> TutorReply:
    """Main conversational loop entrypoint.

    Frontend sends the user's utterance and languages; the backend forwards it
    to Agora Conversational AI (or echoes it in stub mode) and returns the
    model reply plus a trace id for debugging. Fluency is updated each turn,
    and the familiar/target language mix is passed through as a hint.
    """

    # Input validation and rate limiting
    _validate_language("familiar", msg.familiar_language)
    _validate_language("target", msg.target_language)
    if len(msg.message) > MAX_MESSAGE_LENGTH:
        raise HTTPException(status_code=413, detail="Message too long")

    _rate_limit(msg.user_id)

    state = _get_or_create_session(
        user_id=msg.user_id,
        familiar_language=msg.familiar_language,
        target_language=msg.target_language,
    )
    state = _update_fluency(state, msg.message)
    familiar_pct, target_pct = _language_mix(state.fluency)

    payload: Dict[str, Any] = {
        "user_id": msg.user_id,
        "familiar_language": msg.familiar_language,
        "target_language": msg.target_language,
        "message": msg.message,
        "fluency": state.fluency,
        "language_mix": {
            "familiar_pct": familiar_pct,
            "target_pct": target_pct,
        },
    }
    result = _call_agora_convai(payload)
    return TutorReply(**result)


@app.post("/api/video/token", response_model=VideoTokenResponse)
async def video_token(request: VideoTokenRequest) -> VideoTokenResponse:
    """Provide an RTC token for the Agora Video SDK.

    The frontend requests a token for a given channel + uid, then uses
    `app_id` and `token` to join via the Agora Web Video SDK.
    """

    return _fetch_agora_video_token(channel=request.channel, uid=request.uid)


@app.post("/api/convai/join", response_model=ConvAIJoinResponse)
async def convai_join(body: ConvAIJoinRequest) -> ConvAIJoinResponse:
    """Trigger Agora ConvAI agent to join the same RTC channel as the user.

    The browser should call this after it has successfully joined and published
    to the RTC channel. On success, the ConvAI agent will join that channel
    using `AGORA_AGENT_ID`.
    """

    details = _convai_join_rtc(channel=body.channel, user_uid=body.user_uid)
    return ConvAIJoinResponse(status="joined", details=details)


@app.get("/api/progress", response_model=ProgressSnapshot)
async def progress(user_id: str = Query(..., description="User id for the current session")) -> ProgressSnapshot:
    """Return progress + fluency snapshot for a session.

    Currently derived from the in-memory SessionState; hook these values into
    real analytics and LLM-generated scores when available.
    """

    state = SESSIONS.get(user_id)
    if not state:
        # Default stub values when no session exists yet.
        return ProgressSnapshot(speaking=0.3, listening=0.3, writing=0.3, fluency=0.0)

    # For now, base all three skills on fluency with small offsets.
    fluency = state.fluency
    speaking = min(1.0, fluency + 0.05)
    listening = min(1.0, fluency + 0.1)
    writing = max(0.0, fluency - 0.05)

    return ProgressSnapshot(
        speaking=speaking,
        listening=listening,
        writing=writing,
        fluency=fluency,
    )


@app.get("/api/profile", response_model=Profile)
async def profile(user_id: str = Query(..., description="User id for the current session")) -> Profile:
    """Return a simple profile view for the right-side panel.

    In a real app this would come from persistent user storage.
    """

    state = SESSIONS.get(user_id)
    if not state:
        raise HTTPException(status_code=404, detail="No session found for this user")

    description = (
        f"MisSpoke learner focusing on {state.target_language} with "
        f"background in {state.familiar_language}."
    )

    return Profile(
        user_id=state.user_id,
        description=description,
        familiar_language=state.familiar_language,
        target_language=state.target_language,
        turns=state.turns,
        fluency=state.fluency,
    )


@app.post("/api/writing/score", response_model=WritingScoreResponse)
async def writing_score(body: WritingScoreRequest) -> WritingScoreResponse:
    """Evaluate a writing sample using Groq when available.

    The backend asks Groq to grade the learner's short text and return a JSON
    object with `accuracy` (0.0–1.0) and `feedback`. If Groq is not configured
    or parsing fails, we fall back to a simple length-based heuristic.
    """

    text = body.text.strip()
    if not text:
        return WritingScoreResponse(accuracy=0.0, feedback="Try writing at least one word or sentence.")

    # 1) Try Groq if configured
    if GROQ_API_KEY:
        system_prompt = (
            "You are an expert writing tutor. Given a short learner writing sample, "
            "evaluate how accurate and natural it is in the specified target language. "
            "Respond ONLY with a compact JSON object of the form "
            "{\"accuracy\": 0.xx, \"feedback\": \"short sentence\"}. "
            "accuracy is a float between 0.0 and 1.0 (1.0 is perfect)."
        )
        user_prompt = (
            f"Target language: {body.target_language}\n"
            f"Writing sample: {text}"
        )

        try:
            response = requests.post(
                GROQ_API_URL,
                headers={
                    "Authorization": f"Bearer {GROQ_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": GROQ_MODEL,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    "temperature": 0.3,
                    "max_tokens": 256,
                },
                timeout=20,
            )
            response.raise_for_status()
            data: Dict[str, Any] = response.json()
            choices: List[Dict[str, Any]] = data.get("choices") or []
            if choices:
                content = choices[0].get("message", {}).get("content", "").strip()
                try:
                    parsed = json.loads(content)
                    acc = float(parsed.get("accuracy", 0.0))
                    fb = str(parsed.get("feedback", ""))
                    if 0.0 <= acc <= 1.0 and fb:
                        return WritingScoreResponse(accuracy=acc, feedback=fb)
                except (ValueError, TypeError, json.JSONDecodeError):
                    logger.warning("Groq writing score JSON parse failed; falling back to heuristic.")
        except requests.RequestException as exc:
            logger.warning("Groq writing score call failed: %s", exc)

    # 2) Fallback heuristic: longer non-space text gets higher scores.
    raw_chars = [ch for ch in text if not ch.isspace()]
    length = len(raw_chars)
    accuracy = max(0.1, min(1.0, length / 40.0))
    feedback = (
        f"Your {body.target_language} writing sample looks okay. "
        f"Try adding more detail and checking spelling to improve accuracy."
    )

    return WritingScoreResponse(accuracy=accuracy, feedback=feedback)


@app.get("/api/summary", response_model=SessionSummary)
async def summary(user_id: str = Query(..., description="User id for the current session")) -> SessionSummary:
    """Return a simple session summary stub based on fluency and turns."""

    state = SESSIONS.get(user_id)
    if not state:
        return SessionSummary(message="Start a session to see your MisSpoke summary.")

    familiar_pct, target_pct = _language_mix(state.fluency)
    message = (
        f"You completed {state.turns} turns practicing {state.target_language}. "
        f"Current fluency is about {state.fluency * 100:.0f}%. "
        f"The tutor is currently using roughly {familiar_pct}% {state.familiar_language} "
        f"and {target_pct}% {state.target_language}."
    )

    return SessionSummary(message=message)


@app.get("/api/config")
async def config() -> Dict[str, Any]:
    """Expose non-sensitive configuration to the frontend.

    Only non-sensitive values are surfaced here; secrets and tokens stay server-side.
    The `channelName` mirrors your Agora ConvAI project channel (AGORA_CHANNEL).
    """
from fastapi import FastAPI
from fastapi.responses import FileResponse
import os

app = FastAPI()

@app.get("/")
def root():
    return FileResponse(os.path.join(os.getcwd(), "index.html"))

    return {
        "appId": AGORA_APP_ID,
        "channelName": AGORA_CHANNEL,
    }
