# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this project does

A single-agent CrewAI system that fetches Israeli news headlines by category. The user picks one of 6 fixed topics; the agent searches only Israeli news sites, returns 5 headlines, and saves results to `search_history.json`. Sites are not reused within the same category across runs — the user must press "מחק היסטוריה" to reset.

## Running the project

**Web UI:**
```powershell
python server.py
# Opens at http://localhost:5000
```

**CLI (direct, for testing):**
```powershell
python start.py "חדשות ספורט"
```

**Dependencies:**
```powershell
pip install flask crewai crewai-tools python-dotenv
```

## Architecture

### Entry points
- `start.py` — agent runner; takes topic from `sys.argv[1]` (server) or defaults to tech news (CLI). Reads `search_history.json` to pick unused sites, runs the CrewAI agent, parses output, saves results.
- `server.py` — Flask server; spawns `start.py` as a subprocess per request and streams stdout to the browser via SSE.
- `templates/index.html` — self-contained terminal-style UI; no build step.

### Agent pipeline (`start.py`)
One agent (`SerperDevTool`) searches up to 5 sites not yet used for the chosen category. Required output format per line:
```
SITE: domain.co.il | UPDATE: one-sentence Hebrew headline
```
Parsed with regex, saved to `search_history.json`, then printed as `[domain] headline` for the UI to detect.

### Site pool per category (`SITES_BY_TOPIC`)
Each of the 6 topics has its own list of 7 Israeli sites. A site is "used" only within its category — the same site can appear in different categories. When all sites for a topic are exhausted, `start.py` prints `SITES_EXHAUSTED:` and exits; the agent does not auto-reset.

### Streaming flow
`POST /run {topic}` → spawns `start.py topic` → stdout lines pushed to `queue.Queue` → `GET /stream` (SSE) drains queue → browser `EventSource` renders lines. Only one concurrent run allowed (`_running` flag).

### `search_history.json` schema
```json
[{ "date": "ISO8601", "category": "חדשות ספורט", "site": "sport5.co.il", "update": "..." }]
```
`DELETE /clear-history` deletes the file entirely.

## Environment variables (`.env`)
```
SERPER_API_KEY=...
OPENAI_API_KEY=...
```
CrewAI uses OpenAI as its LLM backend. Both keys loaded via `python-dotenv`.

## Hebrew / encoding notes
- `start.py` sets `sys.stdout.reconfigure(encoding='utf-8')` — required on Windows.
- Subprocess launched with `PYTHONUNBUFFERED=1` and `PYTHONIOENCODING=utf-8`.
- The UI detects Hebrew per line (`/[֐-׿]/`) and applies `direction: rtl` dynamically.
- Lines starting with `SITES_EXHAUSTED:` are rendered in red; `[site] text` lines render as styled news cards.
