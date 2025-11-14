# MisSpoke

MisSpoke is a dark-mode conversational language tutor that uses Agora Conversational AI and the Agora RTC Video SDK. It gradually shifts from your familiar language to your target language as your fluency improves.

## High-level features

- Welcome screen with MisSpoke robot mascot
- Language selection: choose a familiar language and a target language using "cloud" chips
- Main tutor screen with a large transcript panel, mic + text input, and join/leave call controls
- Right-side mode rail: profile, video mode, writing mode (canvas), and progress view
- Fluency-aware language mixing (90/10 → 80/20 → 70/30 → 50/50) based on turns/fluency

## Getting started

### 1. Install dependencies

From the repo root:

```bash
pip install -r requirements.txt
```

### 2. Configure (optional) Agora and ConvAI env vars

The FastAPI backend integrates with Agora Conversational AI and video via environment variables. To use real services, provide at least:

- `AGORA_APP_ID`
- `AGORA_TOKEN_SERVER_URL` pointing to your token server
- `AGORA_CONVAI_CHAT_URL`
- `AGORA_CONVAI_API_KEY`

If these are not set, the backend falls back to safe local stubs (echo replies, dummy video tokens) so you can still explore the flows.

### 3. Run the backend + web UI

From the repo root:

```bash
uvicorn app:app --reload
```

Then open the main interface in your browser:

- `http://127.0.0.1:8000/`

The SPA under `static/` will drive the landing, tutor chat, progress dashboard, and session summary using the REST APIs.
