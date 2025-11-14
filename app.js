(function () {
  const API_BASE = ""; // same origin

  function stripEmoji(text) {
    if (!text) return text;
    try {
      // Remove common emoji ranges so they are not spoken out loud.
      return text.replace(/[\u{1F300}-\u{1FAFF}\u{2600}-\u{26FF}\u{2700}-\u{27BF}]/gu, "");
    } catch (e) {
      // Fallback for environments without unicode regex support
      return text;
    }
  }

  function speakText(text) {
    if (typeof window === "undefined") return;
    if (!("speechSynthesis" in window) || typeof window.SpeechSynthesisUtterance === "undefined") {
      console.warn("MisSpoke TTS: speechSynthesis not supported in this browser.");
      return;
    }
    if (!text) return;
    const cleaned = stripEmoji(text);
    if (!cleaned.trim()) return;
    try {
      console.log("MisSpoke TTS speaking:", cleaned);
      window.speechSynthesis.cancel();
      const utterance = new SpeechSynthesisUtterance(cleaned);
      utterance.rate = 1.0;
      utterance.pitch = 1.0;
      window.speechSynthesis.speak(utterance);
    } catch (e) {
      console.warn("MisSpoke TTS error:", e);
    }
  }

  // Screens
  const screenWelcome = document.getElementById("screen-welcome");
  const screenLanguages = document.getElementById("screen-languages");
  const screenTutor = document.getElementById("screen-tutor");

  // Language selection
  const familiarCloudRow = document.getElementById("cloud-familiar");
  const targetCloudRow = document.getElementById("cloud-target");
  const nicknameInput = document.getElementById("nickname-input");
  const btnGetStarted = document.getElementById("btn-get-started");
  const btnGo = document.getElementById("btn-go");
  const mixPreview = document.getElementById("mix-preview");

  // Tutor + chat
  const sessionLabel = document.getElementById("session-label");
  const chatLog = document.getElementById("chat-log");
  const chatInput = document.getElementById("chat-input");
  const btnSend = document.getElementById("btn-send");
  const btnMic = document.getElementById("btn-mic");
  const btnJoinCall = document.getElementById("btn-join-call");
  const btnLeaveCall = document.getElementById("btn-leave-call");
  const btnVoiceTest = document.getElementById("btn-voice-test");

  // Right-side panel
  const modeButtons = Array.from(document.querySelectorAll(".mode-btn"));
  const modeViews = {
    profile: document.getElementById("mode-profile"),
    video: document.getElementById("mode-video"),
    writing: document.getElementById("mode-writing"),
    progress: document.getElementById("mode-progress"),
    home: null,
  };

  const profileText = document.getElementById("profile-text");
  const metricSpeaking = document.getElementById("metric-speaking");
  const metricListening = document.getElementById("metric-listening");
  const metricWriting = document.getElementById("metric-writing");
  const metricFluency = document.getElementById("metric-fluency");
  const summaryText = document.getElementById("summary-text");
  const btnRefreshSummary = document.getElementById("btn-refresh-summary");

  // Video
  const localVideoSlot = document.getElementById("local-video");
  const remoteVideoSlot = document.getElementById("remote-video");

  // Writing
  const writingCanvas = document.getElementById("writing-canvas");
  const btnClearWriting = document.getElementById("btn-clear-writing");
  const btnScoreWriting = document.getElementById("btn-score-writing");
  const writingInput = document.getElementById("writing-input");
  const writingFeedback = document.getElementById("writing-feedback");

  const state = {
    userId: randomId(),
    familiarLanguage: null,
    targetLanguage: null,
    nickname: "",
    inCall: false,
    // Separate numeric uid for Agora RTC (must be numeric for buildTokenWithUid).
    rtcUid: Math.floor(Math.random() * 1000000000).toString(),
  };

  const agora = {
    client: null,
    localTracks: [],
    joined: false,
  };

  // Status helpers are no-ops for now but wired for future UI chips.
  function setMicStatus(_mode) {}
  function setVideoStatus(_mode) {}

  function randomId() {
    return "u_" + Math.random().toString(36).slice(2, 10);
  }

  function setScreen(name) {
    [screenWelcome, screenLanguages, screenTutor].forEach((el) => {
      if (!el) return;
      el.classList.add("hidden");
    });

    if (name === "welcome" && screenWelcome) screenWelcome.classList.remove("hidden");
    if (name === "languages" && screenLanguages) screenLanguages.classList.remove("hidden");
    if (name === "tutor" && screenTutor) screenTutor.classList.remove("hidden");
  }

  function setActiveCloud(rowEl, lang) {
    if (!rowEl) return;
    const buttons = Array.from(rowEl.querySelectorAll(".cloud"));
    buttons.forEach((btn) => {
      const v = btn.getAttribute("data-lang");
      btn.classList.toggle("active", v === lang);
    });
  }

  async function apiGet(path) {
    const res = await fetch(API_BASE + path, {
      method: "GET",
      headers: {
        "Accept": "application/json",
      },
    });
    if (!res.ok) {
      throw new Error(`GET ${path} failed: ${res.status}`);
    }
    return res.json();
  }

  async function apiPost(path, body) {
    const res = await fetch(API_BASE + path, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Accept": "application/json",
      },
      body: JSON.stringify(body),
    });
    if (!res.ok) {
      const text = await res.text();
      throw new Error(`POST ${path} failed: ${res.status} ${text}`);
    }
    return res.json();
  }

  function appendBubble(role, text) {
    if (!chatLog) return;
    const div = document.createElement("div");
    div.className = `bubble ${role}`;
    div.textContent = text;
    chatLog.appendChild(div);
    chatLog.scrollTop = chatLog.scrollHeight;

    // Browser TTS is disabled; Azure Speech handles audio on the backend now.
  }

  async function sendTutorMessage() {
    const text = (chatInput && chatInput.value.trim()) || "";
    if (!text || !state.familiarLanguage || !state.targetLanguage) return;

    appendBubble("user", text);
    chatInput.value = "";

    // Show a loading bubble while waiting for MisSpoke's reply / Azure voice.
    let loadingDiv = null;
    if (chatLog) {
      loadingDiv = document.createElement("div");
      loadingDiv.className = "bubble bot loading";
      loadingDiv.textContent = "MisSpoke is thinking...";
      chatLog.appendChild(loadingDiv);
      chatLog.scrollTop = chatLog.scrollHeight;
    }

    try {
      const payload = {
        user_id: state.userId,
        familiar_language: state.familiarLanguage,
        target_language: state.targetLanguage,
        message: text,
      };
      const data = await apiPost("/api/tutor/message", payload);
      const reply = data.reply || "(no reply)";

      if (loadingDiv && loadingDiv.parentNode) {
        loadingDiv.parentNode.removeChild(loadingDiv);
      }

      appendBubble("bot", reply);
      await refreshProgress();
      await refreshSummary();
    } catch (err) {
      console.error(err);
      if (loadingDiv && loadingDiv.parentNode) {
        loadingDiv.parentNode.removeChild(loadingDiv);
      }
      appendBubble("bot", "Sorry, I couldn't reach the MisSpoke tutor service.");
    }
  }

  async function refreshProgress() {
    try {
      const params = new URLSearchParams({ user_id: state.userId });
      const data = await apiGet(`/api/progress?${params.toString()}`);
      metricSpeaking.textContent = Math.round(data.speaking * 100) + "%";
      metricListening.textContent = Math.round(data.listening * 100) + "%";
      metricWriting.textContent = Math.round(data.writing * 100) + "%";
      metricFluency.textContent = Math.round(data.fluency * 100) + "%";
    } catch (err) {
      console.error(err);
    }
  }

  async function refreshSummary() {
    try {
      const params = new URLSearchParams({ user_id: state.userId });
      const data = await apiGet(`/api/summary?${params.toString()}`);
      summaryText.textContent = data.message || "No summary available yet.";
    } catch (err) {
      console.error(err);
      summaryText.textContent = "Unable to load summary from the server.";
    }
  }

  async function startSessionOnServer() {
    if (!state.familiarLanguage || !state.targetLanguage) return;

    state.nickname = nicknameInput ? nicknameInput.value.trim() : "";

    await apiPost("/api/session/start", {
      user_id: state.userId,
      familiar_language: state.familiarLanguage,
      target_language: state.targetLanguage,
    });

    if (sessionLabel) {
      sessionLabel.textContent = `${state.familiarLanguage} → ${state.targetLanguage}`;
    }

    if (chatLog && chatLog.children.length === 0) {
      appendBubble(
        "bot",
        `Hi${state.nickname ? " " + state.nickname : ""}! I'm your MisSpoke tutor. Let's practice ${state.targetLanguage} together.`
      );
    }

    await refreshProgress();
    await refreshSummary();
    await refreshProfile();
  }

  async function refreshProfile() {
    try {
      const params = new URLSearchParams({ user_id: state.userId });
      const profile = await apiGet(`/api/profile?${params.toString()}`);
      profileText.textContent = `${profile.description} Fluency: ${Math.round(
        profile.fluency * 100
      )}%. Turns: ${profile.turns}.`;
    } catch (err) {
      console.error(err);
    }
  }

  async function joinVideoRoom() {
    if (agora.joined) return;

    setVideoStatus("idle");

    let appConfig;
    try {
      appConfig = await apiGet("/api/config");
    } catch (err) {
      console.error(err);
      appendBubble("bot", "Video config is not available from the server.");
      return;
    }

    const appId = appConfig.appId;
    if (!appId) {
      appendBubble("bot", "Agora appId is not configured on the server.");
      return;
    }

    // Use the same channel as your Agora ConvAI project when provided so the
    // web client and ConvAI agent are in the exact same RTC room.
    const channel = appConfig.channelName || `lesson_${(state.targetLanguage || "default").toLowerCase()}`;
    // Use a numeric uid for Agora RTC so token generation works reliably.
    const uid = state.rtcUid;

    let tokenResponse;
    try {
      tokenResponse = await apiPost("/api/video/token", { channel, uid });
    } catch (err) {
      console.error(err);
      appendBubble("bot", "Couldn't retrieve a video token from the server.");
      return;
    }

    const token = tokenResponse.token;

    if (!window.AgoraRTC) {
      appendBubble(
        "bot",
        "Video is configured server-side, but the Agora Web Video SDK is not loaded in the page yet. Add the SDK script tag to enable live video."
      );
      return;
    }

    const AgoraRTC = window.AgoraRTC;

    // Always show local preview.
    agora.client = AgoraRTC.createClient({ mode: "rtc", codec: "vp8" });

    try {
      await agora.client.join(appId, channel, token, uid);

      // Voice-only for now: create microphone (audio) track only so we can
      // verify live audio with the ConvAI agent without worrying about video.
      const microphoneTrack = await AgoraRTC.createMicrophoneAudioTrack();
      agora.localTracks = [microphoneTrack];

      if (localVideoSlot) {
        localVideoSlot.textContent = "Mic connected";
      }

      // Publish local tracks so remote participants (including the ConvAI agent)
      // can receive our audio/video, matching the Agora Web SDK quickstart.
      await agora.client.publish(agora.localTracks);

      // After user has joined/published, ask the ConvAI agent to join the
      // same RTC channel via the backend.
      try {
        await apiPost("/api/convai/join", { channel, user_uid: uid });
      } catch (err) {
        console.error("ConvAI join failed", err);
        appendBubble(
          "bot",
          "Joined RTC channel, but could not start the Agora ConvAI agent. Check server logs for details."
        );
      }

      agora.client.on("user-published", async (user, mediaType) => {
        await agora.client.subscribe(user, mediaType);
        if (mediaType === "video" && remoteVideoSlot) {
          remoteVideoSlot.innerHTML = "";
          const div = document.createElement("div");
          remoteVideoSlot.appendChild(div);
          user.videoTrack && user.videoTrack.play(div);
        }
        if (mediaType === "audio") {
          user.audioTrack && user.audioTrack.play();
        }
      });

      agora.joined = true;
      state.inCall = true;
      setVideoStatus("live");
    } catch (err) {
      console.error(err);
      appendBubble("bot", "There was an error joining the video room.");
      setMicStatus("off");
      setVideoStatus("off");
    }
  }

  async function leaveVideoRoom() {
    if (!agora.joined || !agora.client) return;
    try {
      agora.localTracks.forEach((track) => track.stop && track.stop());
      agora.localTracks.forEach((track) => track.close && track.close());
      agora.localTracks = [];
      await agora.client.leave();
      agora.client = null;
      agora.joined = false;
      state.inCall = false;
      if (localVideoSlot) localVideoSlot.textContent = "Local video";
      if (remoteVideoSlot) remoteVideoSlot.textContent = "Tutor video";
    } catch (err) {
      console.error(err);
    }
  }

  function setupWritingCanvas() {
    if (!writingCanvas) return;

    const ctx = writingCanvas.getContext("2d");
    let drawing = false;
    let lastX = 0;
    let lastY = 0;

    ctx.strokeStyle = "#e5e7eb";
    ctx.lineWidth = 3;
    ctx.lineCap = "round";

    function startDraw(x, y) {
      drawing = true;
      lastX = x;
      lastY = y;
    }

    function draw(x, y) {
      if (!drawing) return;
      ctx.beginPath();
      ctx.moveTo(lastX, lastY);
      ctx.lineTo(x, y);
      ctx.stroke();
      lastX = x;
      lastY = y;
    }

    function stopDraw() {
      drawing = false;
    }

    writingCanvas.addEventListener("mousedown", (e) => {
      e.preventDefault();
      const rect = writingCanvas.getBoundingClientRect();
      startDraw(e.clientX - rect.left, e.clientY - rect.top);
    });

    writingCanvas.addEventListener("mousemove", (e) => {
      e.preventDefault();
      const rect = writingCanvas.getBoundingClientRect();
      draw(e.clientX - rect.left, e.clientY - rect.top);
    });

    window.addEventListener("mouseup", stopDraw);

    writingCanvas.addEventListener("touchstart", (e) => {
      e.preventDefault();
      const t = e.touches[0];
      const rect = writingCanvas.getBoundingClientRect();
      startDraw(t.clientX - rect.left, t.clientY - rect.top);
    });

    writingCanvas.addEventListener("touchmove", (e) => {
      e.preventDefault();
      const t = e.touches[0];
      const rect = writingCanvas.getBoundingClientRect();
      draw(t.clientX - rect.left, t.clientY - rect.top);
    });

    window.addEventListener("touchend", stopDraw);

    if (btnClearWriting) {
      btnClearWriting.addEventListener("click", () => {
        ctx.clearRect(0, 0, writingCanvas.width, writingCanvas.height);
        if (writingFeedback) {
          writingFeedback.textContent =
            "Write a character or phrase, then tap Check for an estimated accuracy score.";
        }
      });
    }

    if (btnScoreWriting) {
      btnScoreWriting.addEventListener("click", async () => {
        try {
          const sample = writingInput ? writingInput.value.trim() : "";
          if (!sample) {
            if (writingFeedback) {
              writingFeedback.textContent = "Type what you wrote (or a short sentence) in the box above before checking.";
            }
            return;
          }

          const body = {
            user_id: state.userId,
            target_language: state.targetLanguage || "",
            text: sample,
          };
          const result = await apiPost("/api/writing/score", body);
          if (writingFeedback) {
            writingFeedback.textContent =
              `Estimated writing accuracy: ${(result.accuracy * 100).toFixed(0)}%. ` + result.feedback;
          }
        } catch (err) {
          console.error(err);
          if (writingFeedback) {
            writingFeedback.textContent = "Unable to score writing right now. Please try again.";
          }
        }
      });
    }
  }

  function setupMicToggle() {
    let active = false;
    let recognition = null;

    if ("webkitSpeechRecognition" in window || "SpeechRecognition" in window) {
      const Speech = window.SpeechRecognition || window.webkitSpeechRecognition;
      recognition = new Speech();
      recognition.lang = "en-US";
      recognition.interimResults = false;
      recognition.maxAlternatives = 1;
      recognition.continuous = true;

      recognition.onresult = (event) => {
        const transcript = event.results[0][0].transcript;
        if (chatInput) chatInput.value = transcript;
      };

      recognition.onstart = () => setMicStatus("live");
      recognition.onend = () => {
        // In continuous mode, restart automatically while active is true.
        if (active && recognition) {
          try {
            recognition.start();
          } catch (e) {
            // Ignore start errors (e.g., if called too quickly).
          }
        } else {
          setMicStatus("off");
        }
      };
    }

    btnMic.addEventListener("click", () => {
      if (!recognition) {
        appendBubble("bot", "Mic control uses the browser's SpeechRecognition API, which is not available here. Type your message instead.");
        return;
      }

      active = !active;
      if (active) {
        recognition.start();
      } else {
        recognition.stop();
        setMicStatus("off");
      }
    });
  }

  function switchMode(mode) {
    modeButtons.forEach((btn) => {
      btn.classList.toggle("active", btn.getAttribute("data-mode") === mode);
    });

    Object.entries(modeViews).forEach(([key, view]) => {
      if (!view) return;
      view.classList.toggle("hidden", key !== mode);
    });

    if (mode === "home") {
      setScreen("languages");
      switchMode("profile");
    }
  }

  function attachEvents() {
    if (btnGetStarted) {
      btnGetStarted.addEventListener("click", () => {
        setScreen("languages");
      });
    }

    if (familiarCloudRow) {
      familiarCloudRow.addEventListener("click", (e) => {
        const target = e.target.closest(".cloud");
        if (!target) return;
        const lang = target.getAttribute("data-lang");
        state.familiarLanguage = lang;
        setActiveCloud(familiarCloudRow, lang);
      });
    }

    if (targetCloudRow) {
      targetCloudRow.addEventListener("click", (e) => {
        const target = e.target.closest(".cloud");
        if (!target) return;
        const lang = target.getAttribute("data-lang");
        state.targetLanguage = lang;
        setActiveCloud(targetCloudRow, lang);
      });
    }

    if (btnGo) {
      btnGo.addEventListener("click", () => {
        if (!state.familiarLanguage || !state.targetLanguage) {
          if (mixPreview) {
            mixPreview.textContent = "Choose both a familiar language and a target language to continue.";
          }
          return;
        }
        startSessionOnServer().catch(console.error);
        setScreen("tutor");
      });
    }

    if (btnSend) {
      btnSend.addEventListener("click", () => {
        sendTutorMessage().catch(console.error);
      });
    }

    if (chatInput) {
      chatInput.addEventListener("keydown", (e) => {
        if (e.key === "Enter" && !e.shiftKey) {
          e.preventDefault();
          sendTutorMessage().catch(console.error);
        }
      });
    }

    if (btnJoinCall) {
      btnJoinCall.addEventListener("click", () => {
        joinVideoRoom().catch(console.error);
        switchMode("video");
      });
    }

    if (btnLeaveCall) {
      btnLeaveCall.addEventListener("click", () => {
        leaveVideoRoom().catch(console.error);
      });
    }

    if (btnRefreshSummary) {
      btnRefreshSummary.addEventListener("click", () => {
        refreshSummary().catch(console.error);
      });
    }

    if (btnMic) {
      setupMicToggle();
    }

    if (btnVoiceTest) {
      btnVoiceTest.addEventListener("click", () => {
        speakText("This is MisSpoke. If you hear this, text to speech is working.");
      });
    }

    modeButtons.forEach((btn) => {
      btn.addEventListener("click", () => {
        const mode = btn.getAttribute("data-mode");
        if (!mode) return;
        switchMode(mode);
      });
    });

    setupWritingCanvas();
  }

  document.addEventListener("DOMContentLoaded", () => {
    setScreen("welcome");
    attachEvents();
  });
})();
