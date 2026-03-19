# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A browser automation agent powered by Google's Gemini API. Provides CLI (`main.py`) and web UI (`web_app.py`) interfaces to run AI-driven browser tasks using either local Playwright or cloud-based Browserbase.

## Commands

### Setup
```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
playwright install-deps chrome && playwright install chrome
```

### Run CLI
```bash
export GEMINI_API_KEY="..."
python main.py --query "Your task" --env playwright
python main.py --query "Your task" --env browserbase
```

### Run Web UI
```bash
python web_app.py  # serves at http://127.0.0.1:8000
```

### Tests
```bash
pytest                    # all tests
pytest test_agent.py      # single file
pytest test_agent.py -k test_handle_action_click  # single test
```

CI runs pytest on Python 3.10 and 3.11 (`.github/workflows/main.yaml`).

## Architecture

**Entry points** → `main.py` (CLI) and `web_app.py` (FastAPI server with embedded HTML/JS frontend)

**Core loop** (`agent.py` `BrowserAgent`):
1. Send screenshot + conversation history to Gemini API
2. Parse model response for reasoning + function calls (13 predefined actions: click, type, scroll, navigate, etc.)
3. Execute actions via `Computer` interface
4. Capture new screenshot + URL → append to history
5. Repeat until model signals completion

**Browser backends** (`computers/`): Strategy pattern — `Computer` ABC with `PlaywrightComputer` (local) and `BrowserbaseComputer` (cloud, extends Playwright via CDP). Both return `EnvState` (screenshot bytes + URL + optional bSession cookie).

**Event streaming** (`events.py`): `BrowserAgent` emits `ActionEvent`s via callback. `web_app.py` `SessionManager` distributes events to WebSocket clients. Events include: session lifecycle, model reasoning, function call start/finish.

**Web UI**: Single-page app embedded in `web_app.py` `INDEX_HTML`. SessionManager runs the agent in a background thread, bridges events to the asyncio event loop via `run_coroutine_threadsafe`.

## Key Implementation Details

- **Coordinate system**: Gemini returns normalized coords (0–1000); `denormalize_x/y()` converts to pixel coords based on screen size (default 1440×900).
- **Memory optimization**: Only the 3 most recent turns retain screenshots in conversation history.
- **Multi-tab**: New tabs are intercepted and redirected to the current tab (Playwright single-tab limitation).
- **Video recording**: Auto-saved to `artifacts/videos/` as WebM; downloadable via web UI.
- **Retry logic**: 5 attempts with exponential backoff for Gemini API calls.

## Environment Variables

| Variable | Purpose |
|----------|---------|
| `GEMINI_API_KEY` | Required for Gemini API |
| `USE_VERTEXAI` | Set to use Vertex AI instead |
| `VERTEXAI_PROJECT`, `VERTEXAI_LOCATION` | Required if using Vertex AI |
| `BROWSERBASE_API_KEY`, `BROWSERBASE_PROJECT_ID` | Required for Browserbase env |
| `PLAYWRIGHT_HEADLESS` | Set to run Chrome headless |
