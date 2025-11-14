# MisSpoke 🚀🤖🎓

![MisSpoke Logo](https://img.shields.io/badge/MisSpoke-Conversational%20Tutor-blue?style=for-the-badge)
![Dark Mode](https://img.shields.io/badge/Dark%20Mode-enabled-black?style=for-the-badge)
![Python](https://img.shields.io/badge/Made%20with-Python-green?style=for-the-badge)
![FastAPI](https://img.shields.io/badge/Powered%20by-FastAPI-teal?style=for-the-badge)
![Agora RTC](https://img.shields.io/badge/Agora-RTC%20Video%20SDK-blueviolet?style=for-the-badge)

---

MisSpoke is a dark-mode conversational language tutor driven by Agora Conversational AI and Agora RTC Video SDK. It smoothly transitions from your familiar language to your target language, adapting as your fluency increases. Ideal for immersive language learning via chat, voice, and video!

## ✨ High-Level Features

- 🤖 Welcome screen with the MisSpoke robot mascot
- 🌐 Language selection: choose a familiar and a target language using stylish "cloud" chips
- 💬 Main tutor screen: large transcript panel, mic + text input, join/leave call controls
- 📊 Progress dashboard: monitor speaking, listening, writing & fluency
- 🎥 Video mode: agile RTC integration for real-time tutoring
- 📝 Writing canvas mode and profile view for deeper practice
- 🔄 Fluency-aware mixing: dynamically blends the familiar/target language (e.g., 90/10 → 80/20 → ... → 50/50)
- 🛠️ Built-in stubs for easy local development (echo tutor replies and dummy RTC tokens)

---

## 🏁 Getting Started

### 1. Install Dependencies

From the repo root, run:
```bash
pip install -r requirements.txt
```

Required packages:
```
fastapi
uvicorn
requests
python-dotenv
azure-cognitiveservices-speech
agora-token-builder
```

### 2. Configure (Optional) Agora and ConvAI Environment Variables

Set up environment variables for full functionality. At a minimum, provide:
- `AGORA_APP_ID`: Your Agora project App ID
- `AGORA_TOKEN_SERVER_URL`: (optional for local dev) Token server endpoint
- `AGORA_CONVAI_CHAT_URL`: REST endpoint for Agora ConvAI gateway
- `AGORA_CONVAI_API_KEY`: Token for ConvAI backend

> **Tip:** If unset, backend falls back to safe local stubs (echo replies, dummy tokens) so you can explore all flows!

### 3. Run the Backend + Web UI

From the repo root:
```bash
uvicorn app:app --reload
```

Open the SPA in your browser:
- [http://127.0.0.1:8000/](http://127.0.0.1:8000/)

The single-page app under `static/` provides:
- Landing and language selection
- Tutor chat loop
- Progress dashboard
- Session summary

---

## 🔥 Project Architecture

### FastAPI HTTP Service (`app.py`)
- Exposes REST APIs for chat, video, writing, user profile, and progress
- Serves static SPA assets (`static/index.html`, `static/app.js`)
- Handles session state, mixing logic, environment config, and API integration

### SPA Frontend (`static/`)
- HTML/JS, no frontend build step needed
- Connects to backend APIs for chat, video, progress, etc.
- Language mixing and fluency logic supported

### CLI Prototype (`main.py`)
- Documents key UX flows
- Entry point for future dev/agent extension

### RTC Token Example (`TEMP.py`)
- Demonstrates Agora RTC token generation using `agora-token-builder`

## 🚀 REST Endpoints Overview

| Method/Endpoint          | Description                                                         |
|-------------------------|---------------------------------------------------------------------|
| POST `/api/session/start` | Start/resume session; track familiar/target language, fluency      |
| POST `/api/tutor/message` | Conversational loop (chat with AI, update fluency/mix)             |
| POST `/api/video/token`   | Get RTC token for Agora Video SDK                                  |
| GET `/api/progress`       | Fluency/skill snapshot                                             |
| GET `/api/profile`        | User profile for sidebar                                           |
| GET `/api/summary`        | Session summary                                                    |
| POST `/api/writing/score` | Writing sample evaluation (uses Groq or a stub)                    |
| GET `/api/config`         | Expose safe config (App ID, channel)                               |

---

## 🧑‍💻 Development Workflow

1. `pip install -r requirements.txt`
2. Set environment variables as needed
3. `uvicorn app:app --reload`
4. Browse to [http://127.0.0.1:8000/](http://127.0.0.1:8000/) and start learning!

Optional: Run CLI doc tool:
```bash
python main.py
```

---

## 📚 Further Reference

- [WARP.md](https://github.com/git-ksupriya/MisSpoke/blob/main/WARP.md): In-depth architecture, workflow, and extension guidance for developers/agents.
- Source code: [app.py](https://github.com/git-ksupriya/MisSpoke/blob/main/app.py) | [main.py](https://github.com/git-ksupriya/MisSpoke/blob/main/main.py) | [TEMP.py](https://github.com/git-ksupriya/MisSpoke/blob/main/TEMP.py)
- Requirements: [requirements.txt](https://github.com/git-ksupriya/MisSpoke/blob/main/requirements.txt)

---

## 🗒️ Stickers & Badges

![Open Source](https://img.shields.io/badge/Open%20Source-GitHub-brightgreen?style=for-the-badge)
![Agora AI](https://img.shields.io/badge/Agora%20Conversational%20AI-integrated-blue?style=for-the-badge)
![FastAPI](https://img.shields.io/badge/FastAPI-lightning?style=for-the-badge)
![Fluency Progression](https://img.shields.io/badge/Fluency-Progression-yellow?style=for-the-badge)
![AI Powered](https://img.shields.io/badge/AI-Powered-purple?style=for-the-badge)

---

## 📢 Contributing & Issues

Contributions welcome! See future roadmaps and flows in [`main.py`](https://github.com/git-ksupriya/MisSpoke/blob/main/main.py) and submit a PR or issue as you see fit.

---

## 📖 License

_Unspecified (add a LICENSE.md for clarification)._

---

### Happy Learning! 🎉🌍📈