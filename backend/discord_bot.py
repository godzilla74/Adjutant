# backend/discord_bot.py
"""Discord bot integration — Gateway WebSocket, @mention routing, review button handling."""
import asyncio
import logging
import mimetypes
import re
from typing import Callable, Awaitable

import httpx

logger = logging.getLogger(__name__)

_DISCORD_INTERACTION_COMPONENT = 3


class DiscordBot:
    _MAX_LEN = 2000

    def __init__(
        self,
        token: str,
        notification_channel_id: int,
        directive_callback: Callable[[str | None, str], Awaitable[None]],
        resolve_review_fn: Callable[[int, str], None],
        broadcast_fn: Callable[[dict], Awaitable[None]],
        on_review_approved_fn: Callable[[int], Awaitable[None]] | None = None,
    ):
        self._token = token
        self.notification_channel_id = notification_channel_id
        self._directive_callback = directive_callback
        self.resolve_review_fn = resolve_review_fn
        self.broadcast_fn = broadcast_fn
        self._on_review_approved_fn = on_review_approved_fn
        self._pending_products: dict[str | None, object] = {}
        self._bot_user_id: int | None = None
        self._client = None

    async def send_long_message(self, target, text: str) -> None:
        """Send text to a discord Messageable, splitting at 2000-char limit."""
        if len(text) <= self._MAX_LEN:
            await target.send(text)
            return
        remaining = text
        while remaining:
            if len(remaining) <= self._MAX_LEN:
                await target.send(remaining)
                break
            split_at = remaining.rfind('\n\n', 0, self._MAX_LEN)
            if split_at == -1:
                split_at = remaining.rfind('\n', 0, self._MAX_LEN)
            if split_at == -1:
                split_at = self._MAX_LEN
            await target.send(remaining[:split_at].rstrip())
            remaining = remaining[split_at:].lstrip()

    async def notify(self, event: dict) -> None:
        """Forward relevant backend events to Discord."""
        event_type = event.get("type")
        product_id = event.get("product_id")

        if event_type == "agent_done":
            if product_id in self._pending_products:
                thread = self._pending_products.pop(product_id)
                content = event.get("content", "")
                if content:
                    try:
                        await self.send_long_message(thread, content)
                    except Exception as e:
                        logger.warning("Discord notify agent_done failed: %s", e)

        elif event_type == "activity_done":
            if not self.notification_channel_id or not self._client:
                return
            try:
                channel = self._client.get_channel(self.notification_channel_id)
                if channel is None:
                    channel = await self._client.fetch_channel(self.notification_channel_id)
                workstream_name = event.get("workstream_name", "")
                if workstream_name:
                    msg = f"✅ {workstream_name} complete. View the full report in Adjutant under Reports."
                else:
                    summary = event.get("summary", "")
                    msg = f"✅ Agent finished: {summary[:400]}" if summary else ""
                if msg:
                    await channel.send(msg)
            except Exception as e:
                logger.warning("Discord notify activity_done failed: %s", e)

        elif event_type == "review_item_added":
            item = event.get("item", {})
            await self._send_review_item(item)

    async def _send_review_item(self, item: dict) -> None:
        if not self.notification_channel_id or not self._client:
            return
        import discord as _discord

        item_id = item.get("id")
        title = item.get("title", "Review item")
        description = item.get("description", "")
        risk_label = item.get("risk_label", "")

        text = f"📋 **Review Required**\n\n**{title}**"
        if risk_label:
            text += f"\n\n⚠️ {risk_label}"
        if description:
            text += f"\n\n{description}"
        if len(text) > self._MAX_LEN:
            text = text[:self._MAX_LEN - 3] + "…"

        class ReviewView(_discord.ui.View):
            def __init__(self_view):
                super().__init__(timeout=None)

            @_discord.ui.button(label="✅ Approve", style=_discord.ButtonStyle.green,
                                custom_id=f"approve:{item_id}")
            async def approve_btn(self_view, interaction: _discord.Interaction,
                                  button: _discord.ui.Button):
                await self._on_interaction(interaction)

            @_discord.ui.button(label="❌ Reject", style=_discord.ButtonStyle.red,
                                custom_id=f"reject:{item_id}")
            async def reject_btn(self_view, interaction: _discord.Interaction,
                                 button: _discord.ui.Button):
                await self._on_interaction(interaction)

        try:
            channel = self._client.get_channel(self.notification_channel_id)
            if channel is None:
                channel = await self._client.fetch_channel(self.notification_channel_id)
            await channel.send(text, view=ReviewView())
        except Exception as e:
            logger.warning("Discord _send_review_item failed: %s", e)

    async def _on_message(self, message) -> None:
        """Handle an incoming Discord message — called by the on_message event."""
        if not self._client:
            return
        if message.author.bot:
            return

        raw_text = message.content or ""
        text = re.sub(r'<@!?\d+>\s*', '', raw_text).strip()

        file_ref: str | None = None
        if hasattr(message, 'attachments') and message.attachments:
            att = message.attachments[0]
            try:
                local_path, mime = await self._download_attachment(att)
                file_ref = f"[Attached file: {local_path} ({mime})]"
            except Exception as e:
                logger.warning("Failed to download Discord attachment: %s", e)

        if not text and not file_ref:
            return

        # Create a thread for the reply using duck typing (works with both real
        # discord.TextChannel and MagicMock objects in tests)
        try:
            thread = await message.create_thread(
                name="Adjutant", auto_archive_duration=60
            )
        except Exception:
            thread = message.channel

        self._pending_products[None] = thread

        parts = [p for p in [file_ref, text] if p]
        await self._directive_callback(None, "\n\n".join(parts))

    async def _on_interaction(self, interaction) -> None:
        """Handle a Discord button interaction."""
        custom_id = ""
        if hasattr(interaction, "data") and interaction.data:
            custom_id = interaction.data.get("custom_id", "")

        if ":" not in custom_id:
            return
        action_str, item_id_str = custom_id.split(":", 1)
        try:
            item_id = int(item_id_str)
        except ValueError:
            return

        try:
            await interaction.response.defer()
        except Exception:
            pass

        if action_str == "approve":
            self.resolve_review_fn(item_id, "approved")
            await self.broadcast_fn({"type": "review_resolved", "review_item_id": item_id, "action": "approved"})
            try:
                await interaction.edit_original_response(content="✅ Approved", view=None)
            except Exception as e:
                logger.warning("Discord edit_original_response failed: %s", e)
            if self._on_review_approved_fn:
                await self._on_review_approved_fn(item_id)
        elif action_str == "reject":
            self.resolve_review_fn(item_id, "skipped")
            await self.broadcast_fn({"type": "review_resolved", "review_item_id": item_id, "action": "skipped"})
            try:
                await interaction.edit_original_response(content="❌ Rejected", view=None)
            except Exception as e:
                logger.warning("Discord edit_original_response failed: %s", e)

    async def _download_attachment(self, attachment) -> tuple[str, str]:
        from backend.uploads import save_uploaded_file
        filename = attachment.filename or "discord_file"
        mime = mimetypes.guess_type(filename)[0] or "application/octet-stream"
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.get(attachment.url)
            resp.raise_for_status()
        local_path = save_uploaded_file(filename, resp.content)
        return str(local_path), mime

    async def start(self) -> None:
        """Connect to Discord Gateway and process events."""
        if not self._token:
            logger.info("Discord not configured — disabled")
            return

        import discord as _discord

        intents = _discord.Intents.default()
        intents.message_content = True

        while True:
            self._client = _discord.Client(intents=intents)

            @self._client.event
            async def on_ready():
                self._bot_user_id = self._client.user.id
                logger.info("Discord connected as %s", self._client.user)

            @self._client.event
            async def on_message(message: _discord.Message):
                if self._client.user not in message.mentions:
                    return
                await self._on_message(message)

            @self._client.event
            async def on_interaction(interaction: _discord.Interaction):
                if interaction.type == _discord.InteractionType.component:
                    await self._on_interaction(interaction)

            try:
                await self._client.start(self._token)
            except asyncio.CancelledError:
                try:
                    await self._client.close()
                except Exception:
                    pass
                raise
            except Exception as e:
                logger.warning("Discord connection error: %s — reconnecting in 5s", e)
                try:
                    await self._client.close()
                except Exception:
                    pass
                await asyncio.sleep(5)
