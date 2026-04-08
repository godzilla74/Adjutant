# MissionControl — Setup Guide

MissionControl is an autonomous ops dashboard powered by an AI executive assistant (Hannah). She monitors your products, delegates work to specialized sub-agents, surfaces activity in real time, and routes consequential actions through an approval queue before executing them.

---

## Table of Contents

1. [Prerequisites](#1-prerequisites)
2. [Installation](#2-installation)
3. [Configuration](#3-configuration)
4. [First Run](#4-first-run)
5. [Running as a Service](#5-running-as-a-service)
6. [Gmail & Google Calendar Integration](#6-gmail--google-calendar-integration)
7. [Configuring Your Products](#7-configuring-your-products)
8. [Development Workflow](#8-development-workflow)
9. [Architecture Overview](#9-architecture-overview)
10. [Troubleshooting](#10-troubleshooting)

---

## 1. Prerequisites

| Requirement | Minimum | Notes |
|-------------|---------|-------|
| Python | 3.12+ | `python3 --version` |
| Node.js | 18+ | `node --version` |
| npm | 9+ | Comes with Node |
| Git | any | |
| Anthropic API key | — | [console.anthropic.com](https://console.anthropic.com) |

---

## 2. Installation

### Clone the repository

```bash
git clone <your-repo-url> MissionControl
cd MissionControl
```

### Python environment

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### Node environment

```bash
cd ui
npm install
cd ..
```

---

## 3. Configuration

Create a `.env` file in the project root:

```bash
cp .env.example .env   # if it exists, otherwise create manually
```

Edit `.env` with your values:

```env
# Required — get from https://console.anthropic.com
ANTHROPIC_API_KEY=sk-ant-...

# Required — password to access the UI
HANNAH_PASSWORD=choose-a-strong-password

# Optional — port to run on (default: 8001)
# HANNAH_PORT=8001

# Optional — override database location (default: ~/.hannah/missioncontrol.db)
# HANNAH_DB=/path/to/custom/location.db

# ── Social media posting (all optional) ──────────────────────────────────────

# Twitter/X — from developer.twitter.com (OAuth 1.0a User Context)
# TWITTER_API_KEY=
# TWITTER_API_SECRET=
# TWITTER_ACCESS_TOKEN=
# TWITTER_ACCESS_TOKEN_SECRET=

# LinkedIn — OAuth 2.0 access token with w_member_social scope
# Get your author URN: GET https://api.linkedin.com/v2/me (returns "id" field)
# Format: urn:li:person:XXXXXXXXX
# LINKEDIN_ACCESS_TOKEN=
# LINKEDIN_AUTHOR_URN=urn:li:person:XXXXXXXXX

# Facebook — Page access token (from Meta Developer dashboard)
# FACEBOOK_PAGE_ACCESS_TOKEN=
# FACEBOOK_PAGE_ID=

# Instagram — requires a Meta Business/Creator account linked to a Facebook Page
# META_ACCESS_TOKEN=
# INSTAGRAM_BUSINESS_ACCOUNT_ID=
```

**Never commit `.env` to version control.** It is already in `.gitignore`.

---

## 4. First Run

### Using the start script (recommended)

```bash
./start.sh
```

This will:
1. Kill any existing server instance
2. Build the React UI
3. Start the FastAPI backend on `http://0.0.0.0:8001`

Open `http://localhost:8001` in your browser and enter the password you set in `HANNAH_PASSWORD`.

### Skip UI rebuild (faster restarts after backend-only changes)

```bash
./start.sh --no-build
```

### Manual startup (for debugging)

```bash
source .venv/bin/activate
cd ui && npm run build && cd ..
uvicorn backend.main:app --host 0.0.0.0 --port 8001
```

---

## 5. Running as a Service

Set up MissionControl as a systemd user service so it starts automatically and Hannah can restart herself after installing new capabilities.

### Create the service file

```bash
mkdir -p ~/.config/systemd/user

cat > ~/.config/systemd/user/missioncontrol.service << 'EOF'
[Unit]
Description=MissionControl (Hannah)
After=network.target

[Service]
Type=simple
WorkingDirectory=/path/to/MissionControl
EnvironmentFile=/path/to/MissionControl/.env
ExecStart=/path/to/MissionControl/.venv/bin/uvicorn backend.main:app --host 0.0.0.0 --port 8001
Restart=on-failure
RestartSec=3

[Install]
WantedBy=default.target
EOF
```

Replace `/path/to/MissionControl` with your actual path (e.g., `/home/yourname/Code/MissionControl`).

### Enable and start

```bash
systemctl --user daemon-reload
systemctl --user enable missioncontrol
systemctl --user start missioncontrol
```

### Check status / view logs

```bash
systemctl --user status missioncontrol
journalctl --user -u missioncontrol -f
```

### Restart after changes

```bash
systemctl --user restart missioncontrol
```

> **Why this matters:** The systemd service is what allows Hannah to restart herself autonomously after installing new agent skills. Without it, the `restart_server` tool will not function.

---

## 6. Gmail & Google Calendar Integration

Hannah's email and calendar tools run through a local MCP (Model Context Protocol) server. This is optional but unlocks the full power of the email agent.

### 6.1 Set up the Gmail MCP server

```bash
cd /path/to/gmail-mcp   # or wherever you keep this repo
```

The gmail-mcp server must be set up separately. It requires:

1. A **Google Cloud project** with the Gmail API and Google Calendar API enabled
2. An **OAuth 2.0 client ID** (Desktop app type) downloaded as `credentials/client_secret.json`
3. One-time authentication per Google account

Follow the gmail-mcp project's own setup instructions, then run the auth script for each account:

```bash
python setup_auth.py
```

### 6.2 Configure accounts

Edit `config.json` in the gmail-mcp directory:

```json
{
  "your_label": "you@yourdomain.com",
  "product_name": "product@yourdomain.com"
}
```

### 6.3 Run as a service

```bash
cat > ~/.config/systemd/user/gmail-mcp.service << 'EOF'
[Unit]
Description=Gmail MCP Server (SSE)
After=network.target

[Service]
Type=simple
WorkingDirectory=/path/to/gmail-mcp
ExecStart=/path/to/gmail-mcp/.venv/bin/python server_sse.py --host 127.0.0.1 --port 8765
Restart=on-failure
RestartSec=5

[Install]
WantedBy=default.target
EOF

systemctl --user daemon-reload
systemctl --user enable gmail-mcp
systemctl --user start gmail-mcp
```

### 6.4 Verify it's running

```bash
curl http://localhost:8765/sse
# Should respond with: event: endpoint
```

### 6.5 Wire it into Claude Code (optional)

If you also use Claude Code and want it to have Gmail access:

```bash
# ~/.claude/settings.json
{
  "mcpServers": {
    "gmail": {
      "type": "sse",
      "url": "http://localhost:8765/sse"
    }
  }
}
```

> **Note:** Claude Code only loads MCP servers at session start. Restart Claude Code after adding this config.

---

## 7. Configuring Your Products

### Initial products (seed data)

Products are seeded from `backend/seed_data.py` on first run. Edit this file before running for the first time to set up your own products:

```python
PRODUCTS = [
    {"id": "my-product", "name": "My Product", "icon_label": "MP", "color": "#2563eb"},
    # color is any CSS hex color
]

WORKSTREAMS = {
    "my-product": [
        {"name": "Marketing", "status": "running", "display_order": 0},
        {"name": "Product",   "status": "paused",  "display_order": 1},
    ],
}

OBJECTIVES = {
    "my-product": [
        {"text": "Reach 100 users by June 1", "progress_current": 0, "progress_target": 100, "display_order": 0},
    ],
}
```

**Workstream statuses:** `running` | `warn` | `paused`

> **If you've already run the app:** Seed data only inserts on first run. To reset, delete `~/.hannah/missioncontrol.db` and restart.

### Managing products at runtime

Once running, you can ask Hannah directly to manage your products, workstreams, and objectives — she has tools for creating, updating, and deleting all of these.

---

## 8. Development Workflow

### Run tests

```bash
# Backend tests
source .venv/bin/activate
pytest tests/ -v

# Frontend tests
cd ui && npm test
```

### Rebuild the UI

```bash
cd ui && npm run build
```

Or use `./start.sh` which always rebuilds.

### Watch mode (frontend development)

```bash
cd ui && npm run dev
# Vite dev server runs on port 5173 — proxying to backend on 8001 requires vite.config.ts proxy setup
```

### Add a new Hannah tool

1. Add the tool definition to `TOOLS_DEFINITIONS` in `core/tools.py`
2. Add the executor function
3. Wire it into `execute_tool()`
4. Mention it in the system prompt in `core/config.py`
5. Restart the server

### Add a tool via Hannah (self-improvement)

Hannah can extend herself autonomously:

1. Tell Hannah you need a new capability
2. She calls `find_skill()` to search the [skills.sh](https://skills.sh) ecosystem
3. She calls `install_skill()` to install the best match
4. She calls `add_agent_tool()` to scaffold the new tool into `extensions/`
5. She calls `restart_server()` — the service restarts in 3 seconds, client reconnects

Extensions live in `extensions/<tool_name>.py` and are auto-loaded on startup.

---

## 9. Architecture Overview

```
Browser
  │  WebSocket (ws://host/ws)
  ▼
FastAPI (backend/main.py)
  │  auth → product switching → directives → resolve reviews
  │
  ├── SQLite DB (backend/db.py)
  │     ~/.hannah/missioncontrol.db
  │     Tables: products, workstreams, objectives,
  │             activity_events, review_items, messages
  │
  ├── Hannah loop (backend/main.py → _hannah_loop)
  │     Anthropic API (claude-opus-4-6, streaming)
  │     Tools defined in core/tools.py
  │
  ├── Sub-agents (agents/runner.py)
  │     Claude Agent SDK — fresh sub-process per task
  │     email_agent    → gmail-mcp (port 8765)
  │     research_agent → WebSearch + WebFetch
  │     general_agent  → Read + Glob + Grep + Web
  │     extensions/*   → any installed skills
  │
  └── React UI (ui/src/)
        served as static files from ui/dist/
        Components: ProductRail, WorkstreamsPanel,
                    ActivityFeed, ReviewQueue, DirectiveBar
```

### WebSocket message protocol

**Client → Server:**
| Type | Payload | Description |
|------|---------|-------------|
| `auth` | `{password}` | Authenticate |
| `switch_product` | `{product_id}` | Change active product |
| `directive` | `{product_id, content}` | Send instruction to Hannah |
| `resolve_review` | `{review_item_id, action}` | Approve or skip a queued action |

**Server → Client:**
| Type | Description |
|------|-------------|
| `auth_ok` / `auth_fail` | Auth result |
| `init` | Product list on connect |
| `product_data` | Full state for a product |
| `directive_echo` | Confirms your directive was received |
| `hannah_token` | Streaming response chunk |
| `hannah_done` | Full response complete |
| `activity_started` | Agent task began |
| `activity_done` | Agent task finished |
| `review_item_added` | New item in approval queue |
| `review_resolved` | Item approved or skipped |

### Database

SQLite with WAL mode. Default location: `~/.hannah/missioncontrol.db`

Override with `HANNAH_DB` env var (used in tests for isolation).

### Extensions system

New tools can be added without editing core files. Each extension is a single Python file in `extensions/`:

```python
# extensions/my_tool.py

TOOL_DEFINITION = {
    "name": "my_tool",
    "description": "What this tool does",
    "input_schema": {
        "type": "object",
        "properties": {
            "task": {"type": "string", "description": "What to do"},
            "context": {"type": "string", "description": "Background context"},
        },
        "required": ["task"],
    },
}

async def execute(inputs: dict) -> str:
    task = inputs.get("task", "")
    # ... implementation
    return "result"
```

Extensions are auto-discovered at startup via `pkgutil.iter_modules`.

---

## 10. Troubleshooting

### Hannah doesn't respond to messages

1. Check `HANNAH_PASSWORD` is set: `echo $HANNAH_PASSWORD`
2. Check `ANTHROPIC_API_KEY` is set and valid
3. Check server logs: `journalctl --user -u missioncontrol -f`
4. Look for an error popup in the browser (red alert)

### Email agent fails

1. Verify gmail-mcp is running: `curl http://localhost:8765/sse`
2. Check service status: `systemctl --user status gmail-mcp`
3. Re-run auth if tokens expired: `cd /path/to/gmail-mcp && python setup_auth.py`

### `restart_server` has no effect

The `restart_server` tool requires the systemd service to be set up (section 5). Without it, the scheduled `systemctl` call fails silently.

### Database errors on startup

If you see SQLite schema errors, the database has an old schema. Delete it and restart:

```bash
rm ~/.hannah/missioncontrol.db
./start.sh
```

### Port already in use

```bash
pkill -f "uvicorn backend.main"
./start.sh
```

Or change the port in `.env`:

```env
HANNAH_PORT=8002
```

And update `missioncontrol.service` to match.

### UI shows password gate after page refresh

This is resolved in the current version — the password is stored in `sessionStorage` and auto-submitted on reconnect. If you're seeing it, hard-refresh with `Ctrl+Shift+R` to pick up the latest JS build.

---

## Quick Reference

```bash
# Start (with UI rebuild)
./start.sh

# Start (backend only, faster)
./start.sh --no-build

# Restart via service
systemctl --user restart missioncontrol

# View live logs
journalctl --user -u missioncontrol -f

# Run all tests
source .venv/bin/activate && pytest tests/ -v && cd ui && npm test

# Check gmail-mcp
systemctl --user status gmail-mcp
curl http://localhost:8765/sse
```
