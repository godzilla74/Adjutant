# Adjutant — Setup Guide

Adjutant is your AI chief of staff — it monitors your products, delegates work to specialized sub-agents, and surfaces activity in real time.

---

## Quick Install

**Mac / Linux:**
```bash
curl -fsSL https://adjutantapp.com/install.sh | bash
```

**Windows (PowerShell):**
```powershell
irm https://adjutantapp.com/install.ps1 | iex
```

The installer handles Python 3.12+, Node.js 18+, git, configuration, and service registration automatically. After install, open `http://localhost:8001`.

---

## Managing Adjutant

Once installed, use the `adjutant` CLI:

| Command | Action |
|---------|--------|
| `adjutant start` | Start the service |
| `adjutant stop` | Stop the service |
| `adjutant restart` | Restart the service |
| `adjutant update` | Pull latest, rebuild, restart |
| `adjutant logs` | Tail live logs |
| `adjutant uninstall` | Remove everything |

---

## Configuration

Config lives in:
- **Mac:** `~/Library/Application Support/Adjutant/config.env`
- **Linux:** `~/.config/Adjutant/config.env`
- **Windows:** `%APPDATA%\Adjutant\config.env`

| Variable | Description |
|----------|-------------|
| `ANTHROPIC_API_KEY` | Your Anthropic API key |
| `AGENT_PASSWORD` | Password to access the UI |
| `AGENT_NAME` | Your assistant's name (default: Hannah) |
| `AGENT_OWNER_NAME` | Your first name |
| `AGENT_OWNER_BIO` | About you and your business — injected into the assistant's context |
| `AGENT_DB` | Database path (auto-set by installer) |

After editing config, run `adjutant restart`.

---

## Gmail & Google Calendar Integration

Email and calendar tools require a separate Gmail MCP server. See the gmail-mcp project for setup instructions. Once running, Adjutant connects automatically at `http://localhost:8765`.

---

## Architecture

```
Browser
  │  WebSocket (ws://host/ws)
  ▼
FastAPI backend (backend/main.py)
  │  Config loaded from ADJUTANT_CONFIG path
  │
  ├── SQLite DB
  │     Mac:   ~/Library/Application Support/Adjutant/adjutant.db
  │     Linux: ~/.config/Adjutant/adjutant.db
  │     Win:   %APPDATA%\Adjutant\adjutant.db
  │
  ├── Hannah loop → Anthropic API (claude-opus-4-6, streaming)
  │
  ├── Sub-agents (agents/runner.py)
  │     email_agent / research_agent / general_agent / extensions/*
  │
  └── React UI (ui/dist/) — served as static files
```

---

## Development

```bash
# Run tests
source .venv/bin/activate && pytest tests/ -v
cd ui && npm test

# Rebuild UI
cd ui && npm run build

# Start manually (dev mode)
source .venv/bin/activate
ADJUTANT_CONFIG=.env uvicorn backend.main:app --host 0.0.0.0 --port 8001
```

---

## Troubleshooting

**Adjutant doesn't respond:** Check `adjutant logs` and verify `ANTHROPIC_API_KEY` is set correctly in `config.env`.

**Email agent fails:** Verify gmail-mcp is running: `curl http://localhost:8765/sse`

**`restart_server` has no effect:** The service must be registered (done automatically by the installer). Run `adjutant restart` manually.

**Port already in use:** Run `adjutant stop`, then `adjutant start`.

**Database errors:** Delete `adjutant.db` from the config directory and restart. All user data will be re-seeded.
