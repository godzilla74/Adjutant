# Adjutant

**A self-hosted AI executive assistant that runs on your machine, manages your work, and asks before it acts.**

Adjutant gives you a named AI assistant — think Chief of Staff, not chatbot. You tell it what to work on. It delegates to specialized sub-agents, handles research and email, drafts content with your brand voice, and queues anything consequential for your approval before it goes out.

Everything runs locally. Your data stays on your machine. No SaaS accounts, no monthly fees beyond API usage.

---

## What it does

**Works across multiple products or businesses** — each with its own workstreams, goals, and brand configuration. Switch between them from the sidebar.

**Delegates complex work to sub-agents** — research, writing, email, and browser tasks run in parallel without blocking the main conversation.

**Manages an approval queue** — emails to clients, social posts, and anything public-facing land in a review queue first. Nothing goes out without your sign-off.

**Tracks objectives with progress** — set measurable goals (e.g. "500 LinkedIn followers by June") and the agent updates progress as it completes related work.

**Automates browser tasks** — form filling, directory submissions, data extraction — using a visible headed browser so you can see what's happening.

**Connects to Gmail** — reads, searches, drafts, and sends email on your behalf.

**Extends itself** — install agent skills from [skills.sh](https://skills.sh), add MCP servers, or scaffold new tools and restart without touching the code.

---

## Screenshots

> Chat with your agent, review its activity, and manage your approval queue — all in one interface.

*Coming soon.*

---

## Installation

**Requirements:** Python 3.12+, Node.js 18+, Git, an Anthropic API key

### Mac / Linux

```bash
curl -fsSL https://adjutantapp.com/install.sh | bash
```

### Windows (PowerShell)

```powershell
irm https://adjutantapp.com/install.ps1 | iex
```

The installer will:
1. Check and install missing dependencies
2. Clone the repo to `~/adjutant`
3. Ask for your assistant's name, a login password, and your Anthropic API key
4. Ask about your first product to seed the workspace
5. Build the UI, register a background service, and open the app in your browser

The app runs at `http://localhost:8001`.

---

## CLI

```bash
adjutant start      # Start the service
adjutant stop       # Stop the service
adjutant restart    # Restart the service
adjutant update     # Pull latest and rebuild
adjutant logs       # Tail the log file
adjutant uninstall  # Remove everything
```

---

## Configuration

Config lives at `~/.config/Adjutant/config.env` (Linux) or `~/Library/Application Support/Adjutant/config.env` (Mac).

| Variable | Description |
|---|---|
| `ANTHROPIC_API_KEY` | Your Anthropic API key |
| `AGENT_PASSWORD` | Login password for the web UI |
| `AGENT_NAME` | Your assistant's name |
| `AGENT_OWNER_NAME` | Your name (used in the system prompt) |
| `AGENT_OWNER_BIO` | Background context about you and your work |
| `ADJUTANT_SEED_PRODUCT_ID` | Slug for your initial product (e.g. `my-product`) |
| `ADJUTANT_SEED_PRODUCT_NAME` | Display name for your initial product |
| `ADJUTANT_SEED_PRODUCT_DESC` | Description used to AI-generate starter workstreams |

Models are configurable per-product in the Settings sidebar. You can set different models for the main agent and sub-agents.

---

## Architecture

```
Browser (React + TypeScript + Tailwind)
    │ WebSocket
    ▼
FastAPI backend (Python 3.12)
    ├── Main agent loop (Anthropic Claude API, streaming)
    ├── Sub-agent runners (research, general, email)
    ├── Tool executor (20+ built-in tools)
    ├── MCP server manager (stdio + remote)
    └── SQLite (messages, events, review queue, products)
```

**Runs as a system service** — LaunchAgent on macOS, systemd user service on Linux — with automatic restart on failure.

---

## Agent tools

The main agent has access to:

| Category | Tools |
|---|---|
| Delegation | `delegate_task`, `email_task` |
| Approval | `create_review_item` |
| Notes | `save_note`, `read_notes` |
| Products | `create_product`, `update_product`, `delete_product` |
| Workstreams | `create_workstream`, `update_workstream_status`, `delete_workstream` |
| Objectives | `create_objective`, `update_objective`, `delete_objective` |
| Content | `draft_social_post`, `setup_social_media` |
| Browser | `browser_task` |
| Extensions | `find_skill`, `install_skill`, `add_agent_tool`, `restart_server` |
| MCP | `manage_mcp_server` |
| Utilities | `get_datetime` |

---

## Extending Adjutant

**Install a skill** — skills.sh packages add new capabilities to sub-agents:
```
find a skill for [task] and install it
```

**Add an MCP server** — connect any MCP-compatible service:
```
Add the GitHub MCP server at https://example.com/mcp
```

**Scaffold a new tool** — the agent can write and activate its own tools:
```
Add a tool that [description of capability]
```

---

## Updating

```bash
adjutant update
```

Or pull directly from the repo and rebuild manually:

```bash
cd ~/adjutant
git fetch origin main && git reset --hard FETCH_HEAD
cd ui && npm install && npm run build && cd ..
adjutant restart
```

---

## Tech stack

- **Frontend:** React, TypeScript, Tailwind CSS, Vite
- **Backend:** Python 3.12, FastAPI, uvicorn
- **AI:** Anthropic Claude (configurable model per role)
- **Database:** SQLite
- **Sub-agents:** Claude Code agent SDK
- **Browser automation:** Playwright (via browser_task tool)

---

## License

MIT
