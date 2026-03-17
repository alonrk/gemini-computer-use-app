from __future__ import annotations

import asyncio
import threading
from typing import Any

import uvicorn
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from agent import BrowserAgent
from computers import PlaywrightComputer
from events import ActionEvent, build_event

PLAYWRIGHT_SCREEN_SIZE = (1440, 900)
DEFAULT_MODEL = "gemini-2.5-computer-use-preview-10-2025"

INDEX_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Computer Use Runner</title>
  <style>
    :root {
      --bg: #f5efe5;
      --panel: rgba(255, 252, 245, 0.92);
      --ink: #1f2933;
      --muted: #5b6570;
      --accent: #a4471b;
      --accent-strong: #7f2d12;
      --border: rgba(31, 41, 51, 0.12);
      --success: #1d6f42;
      --error: #b42318;
      --shadow: 0 24px 60px rgba(70, 40, 20, 0.12);
    }

    * {
      box-sizing: border-box;
    }

    body {
      margin: 0;
      min-height: 100vh;
      background:
        radial-gradient(circle at top left, rgba(164, 71, 27, 0.18), transparent 28%),
        radial-gradient(circle at bottom right, rgba(36, 101, 84, 0.14), transparent 30%),
        linear-gradient(145deg, #f7f1e7 0%, #efe6d8 46%, #f8f4ed 100%);
      color: var(--ink);
      font-family: "Iowan Old Style", "Palatino Linotype", "Book Antiqua", serif;
    }

    .shell {
      width: min(1100px, calc(100% - 32px));
      margin: 32px auto;
      display: grid;
      gap: 20px;
    }

    .hero,
    .panel {
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 24px;
      box-shadow: var(--shadow);
      backdrop-filter: blur(10px);
    }

    .hero {
      padding: 28px;
      position: relative;
      overflow: hidden;
    }

    .hero::after {
      content: "";
      position: absolute;
      inset: auto -60px -60px auto;
      width: 220px;
      height: 220px;
      background: radial-gradient(circle, rgba(164, 71, 27, 0.16), transparent 68%);
      transform: rotate(18deg);
      pointer-events: none;
    }

    .eyebrow {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      padding: 6px 12px;
      border-radius: 999px;
      background: rgba(164, 71, 27, 0.1);
      color: var(--accent-strong);
      font-family: "Avenir Next", "Segoe UI", sans-serif;
      font-size: 12px;
      font-weight: 700;
      letter-spacing: 0.08em;
      text-transform: uppercase;
    }

    h1 {
      margin: 18px 0 8px;
      font-size: clamp(2rem, 4vw, 3.4rem);
      line-height: 1.04;
      font-weight: 700;
    }

    .subtitle {
      margin: 0;
      max-width: 720px;
      color: var(--muted);
      font-size: 1.05rem;
      line-height: 1.6;
      font-family: "Avenir Next", "Segoe UI", sans-serif;
    }

    .layout {
      display: grid;
      grid-template-columns: minmax(300px, 380px) minmax(0, 1fr);
      gap: 20px;
    }

    .panel {
      padding: 22px;
    }

    .panel h2 {
      margin: 0 0 18px;
      font-size: 1.2rem;
    }

    label {
      display: block;
      margin-bottom: 16px;
      font-family: "Avenir Next", "Segoe UI", sans-serif;
      font-size: 0.95rem;
      font-weight: 600;
    }

    .hint {
      display: block;
      margin-top: 6px;
      color: var(--muted);
      font-size: 0.82rem;
      font-weight: 500;
    }

    input,
    textarea,
    button {
      width: 100%;
      border-radius: 16px;
      border: 1px solid rgba(31, 41, 51, 0.16);
      font: inherit;
    }

    input,
    textarea {
      margin-top: 8px;
      padding: 14px 16px;
      background: rgba(255, 255, 255, 0.9);
      color: var(--ink);
      font-family: "Avenir Next", "Segoe UI", sans-serif;
    }

    textarea {
      min-height: 180px;
      resize: vertical;
    }

    button {
      margin-top: 8px;
      padding: 14px 18px;
      background: linear-gradient(135deg, var(--accent) 0%, #c05a27 100%);
      color: white;
      font-family: "Avenir Next", "Segoe UI", sans-serif;
      font-size: 1rem;
      font-weight: 700;
      cursor: pointer;
      transition: transform 160ms ease, box-shadow 160ms ease, opacity 160ms ease;
      box-shadow: 0 14px 28px rgba(164, 71, 27, 0.28);
    }

    button:hover:not(:disabled) {
      transform: translateY(-1px);
    }

    button:disabled {
      opacity: 0.6;
      cursor: not-allowed;
      box-shadow: none;
    }

    .status-card {
      display: grid;
      gap: 16px;
      margin-bottom: 20px;
      padding: 18px;
      border-radius: 20px;
      background: linear-gradient(180deg, rgba(255,255,255,0.94), rgba(248,242,233,0.94));
      border: 1px solid var(--border);
    }

    .status-row {
      display: flex;
      flex-wrap: wrap;
      gap: 12px;
      align-items: center;
      justify-content: space-between;
      font-family: "Avenir Next", "Segoe UI", sans-serif;
    }

    .badge {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      padding: 6px 12px;
      border-radius: 999px;
      background: rgba(31, 41, 51, 0.08);
      font-size: 0.88rem;
      font-weight: 700;
      text-transform: capitalize;
    }

    .badge.running {
      color: var(--accent-strong);
      background: rgba(164, 71, 27, 0.12);
    }

    .badge.completed {
      color: var(--success);
      background: rgba(29, 111, 66, 0.12);
    }

    .badge.error {
      color: var(--error);
      background: rgba(180, 35, 24, 0.12);
    }

    #status-message,
    #last-url {
      margin: 0;
      color: var(--muted);
      font-family: "Avenir Next", "Segoe UI", sans-serif;
      line-height: 1.5;
      word-break: break-word;
    }

    #log-list {
      list-style: none;
      margin: 0;
      padding: 0;
      display: grid;
      gap: 12px;
      max-height: 60vh;
      overflow: auto;
    }

    .log-entry {
      padding: 14px 16px;
      border-radius: 18px;
      background: rgba(255, 255, 255, 0.88);
      border: 1px solid rgba(31, 41, 51, 0.08);
      font-family: "Avenir Next", "Segoe UI", sans-serif;
      animation: rise 220ms ease;
    }

    .log-entry strong {
      display: block;
      margin-bottom: 4px;
      color: var(--ink);
    }

    .log-meta,
    .log-data {
      margin: 6px 0 0;
      color: var(--muted);
      font-size: 0.9rem;
      line-height: 1.45;
      white-space: pre-wrap;
      word-break: break-word;
    }

    .empty {
      padding: 18px;
      border-radius: 18px;
      background: rgba(255,255,255,0.68);
      border: 1px dashed rgba(31, 41, 51, 0.14);
      color: var(--muted);
      font-family: "Avenir Next", "Segoe UI", sans-serif;
    }

    @keyframes rise {
      from {
        opacity: 0;
        transform: translateY(8px);
      }
      to {
        opacity: 1;
        transform: translateY(0);
      }
    }

    @media (max-width: 840px) {
      .shell {
        width: min(100% - 20px, 1000px);
        margin: 18px auto 24px;
      }

      .layout {
        grid-template-columns: 1fr;
      }

      .hero,
      .panel {
        border-radius: 20px;
      }
    }
  </style>
</head>
<body>
  <main class="shell">
    <section class="hero">
      <span class="eyebrow">Playwright Session Control</span>
      <h1>Run a Gemini computer-use session from the browser.</h1>
      <p class="subtitle">
        Start one local Playwright-backed run at a time, watch the agent reasoning stream in,
        and follow every action the session takes as it moves through the web.
      </p>
    </section>

    <section class="layout">
      <section class="panel">
        <h2>Start Session</h2>
        <form id="run-form">
          <label for="api-key">
            Gemini API key
            <input id="api-key" name="api_key" type="password" autocomplete="off" required>
            <span class="hint">The key is used for the current run only and is not persisted.</span>
          </label>

          <label for="prompt">
            User prompt
            <textarea id="prompt" name="prompt" placeholder="Go to Google and search for the latest AI news." required></textarea>
          </label>

          <button id="run-button" type="submit">Run</button>
        </form>
      </section>

      <section class="panel">
        <div class="status-card">
          <div class="status-row">
            <h2 style="margin:0;">Session Activity</h2>
            <span id="status-badge" class="badge idle">idle</span>
          </div>
          <p id="status-message">No session has started yet.</p>
          <p id="last-url"></p>
        </div>

        <div id="log-empty" class="empty">The action log will appear here as soon as the session starts.</div>
        <ul id="log-list" aria-live="polite"></ul>
      </section>
    </section>
  </main>

  <script>
    const form = document.getElementById("run-form");
    const runButton = document.getElementById("run-button");
    const statusBadge = document.getElementById("status-badge");
    const statusMessage = document.getElementById("status-message");
    const lastUrl = document.getElementById("last-url");
    const logList = document.getElementById("log-list");
    const logEmpty = document.getElementById("log-empty");
    const seenSequences = new Set();
    let socket;

    function formatData(data) {
      if (!data) {
        return "";
      }
      const clone = { ...data };
      delete clone.sequence;
      if (Object.keys(clone).length === 0) {
        return "";
      }
      return JSON.stringify(clone, null, 2);
    }

    function updateStatus(snapshot) {
      const status = snapshot.status || "idle";
      statusBadge.textContent = status;
      statusBadge.className = `badge ${status}`;
      statusMessage.textContent = snapshot.result_message || (
        status === "running" ? "Session is currently running." : "No session has started yet."
      );
      lastUrl.textContent = snapshot.last_url ? `Last URL: ${snapshot.last_url}` : "";
      runButton.disabled = Boolean(snapshot.active);
    }

    function appendEvent(event) {
      const sequence = event.data && event.data.sequence;
      if (sequence && seenSequences.has(sequence)) {
        return;
      }
      if (sequence) {
        seenSequences.add(sequence);
      }

      logEmpty.hidden = true;

      const item = document.createElement("li");
      item.className = "log-entry";

      const title = document.createElement("strong");
      title.textContent = `${event.type}: ${event.message}`;
      item.appendChild(title);

      const meta = document.createElement("p");
      meta.className = "log-meta";
      meta.textContent = new Date(event.timestamp).toLocaleString();
      item.appendChild(meta);

      const dataText = formatData(event.data);
      if (dataText) {
        const data = document.createElement("pre");
        data.className = "log-data";
        data.textContent = dataText;
        item.appendChild(data);
      }

      logList.appendChild(item);
      logList.scrollTop = logList.scrollHeight;
    }

    async function loadSnapshot() {
      const response = await fetch("/api/session");
      const snapshot = await response.json();
      updateStatus(snapshot);
    }

    function connectEvents() {
      const protocol = window.location.protocol === "https:" ? "wss" : "ws";
      socket = new WebSocket(`${protocol}://${window.location.host}/api/events`);

      socket.addEventListener("message", (message) => {
        const event = JSON.parse(message.data);
        appendEvent(event);
        updateStatus({
          status: event.type === "session_failed" ? "error" :
                  event.type === "session_completed" ? "completed" :
                  event.type === "session_started" ? "running" : statusBadge.textContent,
          result_message: event.message,
          last_url: event.data && event.data.url ? event.data.url : lastUrl.textContent.replace(/^Last URL:\\s*/, ""),
          active: !["session_completed", "session_failed"].includes(event.type)
        });
      });

      socket.addEventListener("close", () => {
        window.setTimeout(connectEvents, 1000);
      });
    }

    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const apiKey = document.getElementById("api-key").value.trim();
      const prompt = document.getElementById("prompt").value.trim();

      if (!apiKey || !prompt) {
        statusMessage.textContent = "A Gemini API key and prompt are both required.";
        statusBadge.textContent = "error";
        statusBadge.className = "badge error";
        return;
      }

      try {
        runButton.disabled = true;
        seenSequences.clear();
        logList.innerHTML = "";
        logEmpty.hidden = false;
        const response = await fetch("/api/run", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ api_key: apiKey, prompt })
        });

        const payload = await response.json();
        if (!response.ok) {
          throw new Error(payload.detail || "Unable to start session.");
        }

        await loadSnapshot();
      } catch (error) {
        runButton.disabled = false;
        statusBadge.textContent = "error";
        statusBadge.className = "badge error";
        statusMessage.textContent = error.message;
      }
    });

    loadSnapshot();
    connectEvents();
  </script>
</body>
</html>
"""


class RunRequest(BaseModel):
    api_key: str
    prompt: str


class SessionManager:
    def __init__(self):
        self._lock = threading.Lock()
        self._status = "idle"
        self._result_message = "No session has started yet."
        self._last_url: str | None = None
        self._events: list[ActionEvent] = []
        self._thread: threading.Thread | None = None
        self._listeners: set[asyncio.Queue[dict[str, Any]]] = set()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._sequence = 0

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "status": self._status,
                "active": self._thread is not None and self._thread.is_alive(),
                "last_url": self._last_url,
                "result_message": self._result_message,
            }

    def start_session(self, api_key: str, prompt: str, model_name: str = DEFAULT_MODEL):
        cleaned_api_key = api_key.strip()
        cleaned_prompt = prompt.strip()
        if not cleaned_api_key:
            raise ValueError("Gemini API key is required.")
        if not cleaned_prompt:
            raise ValueError("Prompt is required.")

        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                raise RuntimeError("A session is already running.")

            self._status = "running"
            self._result_message = "Starting session..."
            self._last_url = None
            self._events = []
            self._sequence = 0
            self._thread = threading.Thread(
                target=self._run_session,
                args=(cleaned_api_key, cleaned_prompt, model_name),
                daemon=True,
            )
            self._thread.start()

    async def register_listener(self) -> asyncio.Queue[dict[str, Any]]:
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        with self._lock:
            self._loop = asyncio.get_running_loop()
            backlog = [event.to_dict() for event in self._events]
            self._listeners.add(queue)

        for payload in backlog:
            await queue.put(payload)
        return queue

    async def unregister_listener(self, queue: asyncio.Queue[dict[str, Any]]):
        with self._lock:
            self._listeners.discard(queue)

    def _run_session(self, api_key: str, prompt: str, model_name: str):
        try:
            env = PlaywrightComputer(screen_size=PLAYWRIGHT_SCREEN_SIZE)
            with env as browser_computer:
                agent = BrowserAgent(
                    browser_computer=browser_computer,
                    query=prompt,
                    model_name=model_name,
                    api_key=api_key,
                    event_sink=self._publish,
                    safety_mode="terminate",
                    verbose=False,
                )
                agent.agent_loop()
        except Exception as exc:
            if self.snapshot()["status"] not in {"completed", "error"}:
                self._publish(
                    build_event(
                        "session_failed",
                        "Session failed.",
                        {"error": str(exc)},
                    )
                )
        finally:
            with self._lock:
                self._thread = None

    def _publish(self, event: ActionEvent):
        payload = event.to_dict()
        with self._lock:
            self._sequence += 1
            payload["data"] = {**payload["data"], "sequence": self._sequence}

            event = ActionEvent(
                type=payload["type"],
                timestamp=payload["timestamp"],
                message=payload["message"],
                data=payload["data"],
            )
            self._events.append(event)
            self._update_snapshot_from_event(event)
            listeners = list(self._listeners)
            loop = self._loop

        if loop is None:
            return

        for queue in listeners:
            asyncio.run_coroutine_threadsafe(queue.put(payload), loop)

    def _update_snapshot_from_event(self, event: ActionEvent):
        if event.type == "session_started":
            self._status = "running"
            self._result_message = event.message
        elif event.type == "function_call_finished":
            if url := event.data.get("url"):
                self._last_url = url
            self._result_message = event.message
        elif event.type == "model_reasoning":
            self._result_message = event.message
        elif event.type == "session_completed":
            self._status = "completed"
            self._result_message = event.message
            if url := event.data.get("url"):
                self._last_url = url
        elif event.type == "session_failed":
            self._status = "error"
            self._result_message = event.message
            if url := event.data.get("url"):
                self._last_url = url


def create_app(session_manager: SessionManager | None = None) -> FastAPI:
    manager = session_manager or SessionManager()
    app = FastAPI()
    app.state.session_manager = manager

    @app.get("/", response_class=HTMLResponse)
    async def index() -> HTMLResponse:
        return HTMLResponse(INDEX_HTML)

    @app.get("/api/session")
    async def get_session() -> dict[str, Any]:
        return manager.snapshot()

    @app.post("/api/run", status_code=202)
    async def run_session(request: RunRequest) -> dict[str, Any]:
        try:
            manager.start_session(request.api_key, request.prompt)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

        return manager.snapshot()

    @app.websocket("/api/events")
    async def events_socket(websocket: WebSocket):
        await websocket.accept()
        queue = await manager.register_listener()
        try:
            while True:
                payload = await queue.get()
                await websocket.send_json(payload)
        except WebSocketDisconnect:
            pass
        finally:
            await manager.unregister_listener(queue)

    return app


app = create_app()


if __name__ == "__main__":
    uvicorn.run("web_app:app", host="127.0.0.1", port=8000, reload=False)
