# WARP.md

This file provides guidance to WARP (warp.dev) when working with code in this repository.

## Project overview

MisSpoke is a dark-mode conversational language tutor that uses Agora Conversational AI and the Agora RTC Video SDK. It gradually shifts from the learner's familiar language to the target language as fluency improves.

The current codebase is a functional prototype with:
- A FastAPI HTTP service that exposes JSON REST APIs and serves the MisSpoke single-page web app.
- A browser-based SPA (in `static/`) that implements the welcome screen, language selection, and main tutor flows using those APIs.
- A simple CLI entry point that documents intended flows and future integration with a ConvAI/backend stack (referenced as "agorabot" in comments).

## Code architecture and structure

### FastAPI service (`app.py`)

`app.py` defines the backend HTTP API, static file serving, and integration hooks for Agora Conversational AI and video:
- `app = FastAPI(...)` plus CORS middleware; static files are served from `static/`.
- `GET /` serves `static/index.html` (the SPA).
- `POST /api/tutor/message` is the main conversational endpoint; it forwards user messages to Agora Conversational AI via `_call_agora_convai`.
- `POST /api/video/token` retrieves or synthesizes an Agora RTC token via `_fetch_agora_video_token`.
- `GET /api/progress` and `GET /api/summary` return stubbed progress and session summary data.
- `GET /api/config` exposes only non-sensitive config to the browser (currently the Agora `appId`).

Configuration is entirely via environment variables (read with `os.getenv`):
- `AGORA_APP_ID` – Agora project App ID (surfaced to the frontend).
- `AGORA_TOKEN_SERVER_URL` – URL of a token server you control; if omitted, the backend returns a local-only dummy token.
- `AGORA_CONVAI_CHAT_URL` – REST endpoint for your Agora Conversational AI / ConvAI gateway.
- `AGORA_CONVAI_API_KEY` – API key or bearer token used to call the ConvAI gateway.

If the ConvAI variables are unset, `_call_agora_convai` runs in a safe stub mode that simply echoes the learner's message. This keeps the prototype usable without external services.

### SPA frontend (`static/index.html`, `static/app.js`)

The frontend is a lightweight HTML/JS SPA with no build step:
- `static/index.html` defines the layout: session setup, tutor conversation panel with waveform, progress dashboard, video grid, and session summary.
- `static/app.js` wires UI controls to the backend REST APIs:
  - Chat: calls `POST /api/tutor/message` and renders user/tutor bubbles.
  - Progress: polls `GET /api/progress` to update speaking/listening/writing metrics.
  - Summary: requests `GET /api/summary` on load and on "Refresh summary".
  - Video: fetches `GET /api/config` and `POST /api/video/token`, then joins an Agora channel using `window.AgoraRTC` if the Web SDK is loaded.
  - Mic helper: optionally uses the browser `SpeechRecognition`/`webkitSpeechRecognition` API to dictate into the chat box when available.

The SPA assumes the Agora Web Video SDK will be included via a `<script>` tag in `index.html`; if it is missing, the UI still works for chat and dashboards and logs a friendly message.

### CLI prototype (`main.py`)

`main.py` provides a CLI-oriented entry point that documents how the flows from the blueprint map into this prototype:
- `main()` builds a multi-line description using `textwrap.dedent` and prints it.
- The description outlines the key flows (landing, tutor interface, writing practice, progress dashboard, session summary) and explicitly calls out next steps:
  - Hooking this prototype into the existing ConvAI/backend stack used in "agorabot".
  - Adding concrete handlers for `/tutor`, `/writing`, `/progress`, and `/summary`.

This file is useful for future agents as a roadmap for where to extend functionality; treat its bullet list of "Next steps" as high-level product requirements.

### Documentation and dependencies

- `README.md` summarizes the product intent and the main user-facing flows; it should be kept in sync with any major changes to endpoints or overall UX.
- `requirements.txt` lists runtime dependencies: FastAPI, Uvicorn, and `requests`. No development-only tooling (linters, formatters, or test frameworks) is currently specified.

## Development workflow and commands

### Environment setup

Install Python dependencies from the repository root:

- `pip install -r requirements.txt`

(Use your preferred virtual environment approach; nothing in the repo constrains this.)

### Running the FastAPI service and web UI

From the repository root, start the HTTP API and SPA using Uvicorn:

- `uvicorn app:app --reload`

Then open the main tutoring interface in a browser at:

- `http://127.0.0.1:8000/`

The SPA will call the JSON APIs under `/api/*` from the same origin.

### Running the CLI prototype

To print the textual overview of flows and next steps defined in `main.py`:

- `python main.py`

### Linting and tests

- There is currently no configured linter/formatter (e.g., Ruff, Black, Flake8) and no test suite or test framework in the repository.
- Before adding lint or test commands here, first introduce the relevant tools (e.g., via `requirements.txt` and a `tests/` directory) and then document the concrete commands in this section.

### Environment configuration for Agora/ConvAI

At minimum, set the following environment variables before running the app in a real Agora environment (exact values depend on your Agora project and ConvAI gateway):

- `AGORA_APP_ID`
- `AGORA_TOKEN_SERVER_URL` (optional for local prototyping; required for real RTC tokens)
- `AGORA_CONVAI_CHAT_URL`
- `AGORA_CONVAI_API_KEY`

For local development without external services, you can omit these and rely on the backend's stub behavior (echo tutor replies and dummy video tokens).

