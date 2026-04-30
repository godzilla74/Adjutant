# Slack Setup Guide

This guide walks you through creating a Slack app and connecting it to Adjutant.

## Step 1 — Create a Slack App

1. Go to [api.slack.com/apps](https://api.slack.com/apps) and click **Create New App**
2. Choose **From scratch**
3. Name your app (e.g. "Adjutant") and select your workspace
4. Click **Create App**

## Step 2 — Enable Socket Mode

Socket Mode lets your app connect to Slack without a public URL.

1. In the left sidebar, click **Socket Mode**
2. Toggle **Enable Socket Mode** to ON
3. Click **Generate** to create an App-Level Token
4. Name it (e.g. "adjutant-socket"), add the `connections:write` scope, and click **Generate**
5. Copy the token — it starts with `xapp-`

## Step 3 — Add Bot Scopes

1. In the left sidebar, go to **OAuth & Permissions**
2. Scroll to **Bot Token Scopes** and add:
   - `app_mentions:read` — receive @mention events
   - `chat:write` — send messages
   - `channels:read` — list channels
   - `files:read` — access shared files

## Step 4 — Install the App to Your Workspace

1. Still in **OAuth & Permissions**, scroll to the top and click **Install to Workspace**
2. Authorize the app
3. Copy the **Bot User OAuth Token** — it starts with `xoxb-`

## Step 5 — Invite the Bot to Channels

In Slack, create or open a channel and type:

```
/invite @YourAppName
```

Do this for any channel where you want to use the bot, and for the notification channel.

## Step 6 — Connect in Adjutant

1. In Adjutant Settings → Integrations → Slack, paste your **Bot Token** (`xoxb-...`) and **App-Level Token** (`xapp-...`)
2. Click **Connect Slack**
3. Once connected, select your **Notification Channel** from the dropdown
4. @mention your bot in any channel to start sending directives
