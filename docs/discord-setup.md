# Discord Setup Guide

This guide walks you through creating a Discord bot and connecting it to Adjutant.

## Step 1 — Create a Discord Application

1. Go to [discord.com/developers/applications](https://discord.com/developers/applications)
2. Click **New Application**
3. Name your application (e.g. "Adjutant") and click **Create**

## Step 2 — Add a Bot

1. In the left sidebar, click **Bot**
2. Click **Add Bot** and confirm
3. Under **Privileged Gateway Intents**, enable:
   - **Message Content Intent** — required to read message text
   - **Server Members Intent** — optional, for member lookups
4. Click **Save Changes**
5. Click **Reset Token**, confirm, and copy your bot token

## Step 3 — Generate an Invite URL

1. In the left sidebar, click **OAuth2 → URL Generator**
2. Under **Scopes**, check **bot**
3. Under **Bot Permissions**, check:
   - Send Messages
   - Read Message History
   - Use Slash Commands
4. Copy the generated URL and open it in your browser to invite the bot to your server

## Step 4 — Create a Notification Channel

1. In your Discord server, create a text channel (e.g. `#adjutant-notifications`)
2. Ensure the bot has access: right-click the channel → **Edit Channel** → **Permissions** → add your bot with Send Messages permission

## Step 5 — Connect in Adjutant

1. In Adjutant Settings → Integrations → Discord, paste your **Bot Token**
2. Click **Connect Discord**
3. Once connected, select your **Notification Channel** from the dropdown
4. @mention your bot in any channel to start sending directives
