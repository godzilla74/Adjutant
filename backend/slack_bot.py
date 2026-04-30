# backend/slack_bot.py
"""Slack bot integration — Socket Mode, @mention routing, review item approval."""
import asyncio
import logging
import mimetypes
import re
from typing import Callable, Awaitable

import httpx

logger = logging.getLogger(__name__)


class SlackBot:
    _MAX_BLOCK_LEN = 3000

    def __init__(
        self,
        bot_token: str,
        app_token: str,
        notification_channel_id: str,
        directive_callback: Callable[[str | None, str], Awaitable[None]],
        resolve_review_fn: Callable[[int, str], None],
        broadcast_fn: Callable[[dict], Awaitable[None]],
        on_review_approved_fn: Callable[[int], Awaitable[None]] | None = None,
    ):
        self.bot_token = bot_token
        self.app_token = app_token
        self.notification_channel_id = notification_channel_id
        self._directive_callback = directive_callback
        self.resolve_review_fn = resolve_review_fn
        self.broadcast_fn = broadcast_fn
        self._on_review_approved_fn = on_review_approved_fn
        self._pending_products: dict[str | None, tuple[str, str]] = {}
        self._bot_user_id: str | None = None
        self._web_client = None  # initialised in start() after token guard

    async def send_long_message(self, channel: str, text: str, thread_ts: str | None = None) -> None:
        """Send text as Block Kit blocks in a single chat_postMessage call."""
        blocks = []
        remaining = text
        while remaining:
            if len(remaining) <= self._MAX_BLOCK_LEN:
                blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": remaining}})
                break
            split_at = remaining.rfind('\n\n', 0, self._MAX_BLOCK_LEN)
            if split_at == -1:
                split_at = remaining.rfind('\n', 0, self._MAX_BLOCK_LEN)
            if split_at == -1:
                split_at = self._MAX_BLOCK_LEN
            blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": remaining[:split_at].rstrip()}})
            remaining = remaining[split_at:].lstrip()

        try:
            await self._web_client.chat_postMessage(
                channel=channel,
                text=text[:200],
                blocks=blocks,
                thread_ts=thread_ts,
            )
        except Exception as e:
            logger.warning("Slack send_long_message failed: %s", e)

    async def notify(self, event: dict) -> None:
        """Forward relevant backend events to Slack."""
        event_type = event.get("type")
        product_id = event.get("product_id")

        if event_type == "agent_done":
            if product_id in self._pending_products:
                channel, thread_ts = self._pending_products.pop(product_id)
                content = event.get("content", "")
                if content:
                    await self.send_long_message(channel, content, thread_ts=thread_ts)

        elif event_type == "activity_done":
            if not self.notification_channel_id:
                return
            workstream_name = event.get("workstream_name", "")
            if workstream_name:
                msg = f"✅ {workstream_name} complete. View the full report in Adjutant under Reports."
            else:
                summary = event.get("summary", "")
                msg = f"✅ Agent finished: {summary[:400]}" if summary else ""
            if msg:
                try:
                    await self._web_client.chat_postMessage(
                        channel=self.notification_channel_id,
                        text=msg,
                    )
                except Exception as e:
                    logger.warning("Slack notify activity_done failed: %s", e)

        elif event_type == "review_item_added":
            item = event.get("item", {})
            await self._send_review_item(item)

    async def _send_review_item(self, item: dict) -> None:
        if not self.notification_channel_id:
            return
        item_id = item.get("id")
        title = item.get("title", "Review item")
        description = item.get("description", "")
        risk_label = item.get("risk_label", "")

        text = f"*📋 Review Required*\n\n*{title}*"
        if risk_label:
            text += f"\n\n⚠️ {risk_label}"
        if description:
            text += f"\n\n{description}"
        if len(text) > self._MAX_BLOCK_LEN:
            text = text[:self._MAX_BLOCK_LEN - 3] + "…"

        blocks = [
            {"type": "section", "text": {"type": "mrkdwn", "text": text}},
            {
                "type": "actions",
                "block_id": f"review_{item_id}",
                "elements": [
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "✅ Approve"},
                        "style": "primary",
                        "action_id": f"approve:{item_id}",
                        "value": str(item_id),
                    },
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "❌ Reject"},
                        "style": "danger",
                        "action_id": f"reject:{item_id}",
                        "value": str(item_id),
                    },
                ],
            },
        ]
        try:
            await self._web_client.chat_postMessage(
                channel=self.notification_channel_id,
                text=f"Review Required: {title}",
                blocks=blocks,
            )
        except Exception as e:
            logger.warning("Slack _send_review_item failed: %s", e)

    async def _process_event_payload(self, payload: dict) -> None:
        """Dispatch a decoded Socket Mode payload to the appropriate handler."""
        payload_type = payload.get("type")
        if payload_type == "event_callback":
            await self._handle_event(payload)
        elif payload_type == "block_actions":
            await self._handle_block_actions(payload)

    async def _handle_event(self, payload: dict) -> None:
        event = payload.get("event", {})
        if event.get("type") != "app_mention":
            return

        raw_text = event.get("text", "")
        text = re.sub(r'<@[A-Z0-9]+>\s*', '', raw_text).strip()

        channel = event.get("channel", "")
        thread_ts = event.get("thread_ts") or event.get("ts", "")

        file_ref: str | None = None
        for f in event.get("files", []):
            url = f.get("url_private_download") or f.get("url_private")
            if url:
                try:
                    local_path, mime = await self._download_slack_file(url)
                    file_ref = f"[Attached file: {local_path} ({mime})]"
                    break
                except Exception as e:
                    logger.warning("Failed to download Slack attachment: %s", e)

        if not text and not file_ref:
            return

        parts = [p for p in [file_ref, text] if p]
        directive_text = "\n\n".join(parts)

        # Single-slot: only one pending reply at a time. Concurrent @mentions
        # overwrite this entry; the earlier requester won't receive a reply.
        self._pending_products[None] = (channel, thread_ts)
        await self._directive_callback(None, directive_text)

    async def _handle_block_actions(self, payload: dict) -> None:
        actions = payload.get("actions", [])
        if not actions:
            return
        action_id = actions[0].get("action_id", "")
        if ":" not in action_id:
            return
        action_str, item_id_str = action_id.split(":", 1)
        try:
            item_id = int(item_id_str)
        except ValueError:
            return

        channel_id = payload.get("channel", {}).get("id", "")
        msg_ts = payload.get("message", {}).get("ts")

        if action_str == "approve":
            self.resolve_review_fn(item_id, "approved")
            await self.broadcast_fn({"type": "review_resolved", "review_item_id": item_id, "action": "approved"})
            if msg_ts and channel_id:
                try:
                    await self._web_client.chat_update(
                        channel=channel_id, ts=msg_ts, text="✅ Approved", blocks=[]
                    )
                except Exception as e:
                    logger.warning("Slack chat_update failed: %s", e)
            if self._on_review_approved_fn:
                await self._on_review_approved_fn(item_id)
        elif action_str == "reject":
            self.resolve_review_fn(item_id, "skipped")
            await self.broadcast_fn({"type": "review_resolved", "review_item_id": item_id, "action": "skipped"})
            if msg_ts and channel_id:
                try:
                    await self._web_client.chat_update(
                        channel=channel_id, ts=msg_ts, text="❌ Rejected", blocks=[]
                    )
                except Exception as e:
                    logger.warning("Slack chat_update failed: %s", e)

    async def _download_slack_file(self, url: str) -> tuple[str, str]:
        from backend.uploads import save_uploaded_file
        filename = url.split("/")[-1].split("?")[0] or "slack_file"
        mime = mimetypes.guess_type(filename)[0] or "application/octet-stream"
        async with httpx.AsyncClient(
            headers={"Authorization": f"Bearer {self.bot_token}"}, timeout=60
        ) as client:
            resp = await client.get(url)
            resp.raise_for_status()
        local_path = save_uploaded_file(filename, resp.content)
        return str(local_path), mime

    async def start(self) -> None:
        """Connect via Slack Socket Mode and process events."""
        if not self.bot_token or not self.app_token:
            logger.info("Slack not configured — disabled")
            return

        from slack_sdk.web.async_client import AsyncWebClient
        from slack_sdk.socket_mode.websockets import SocketModeClient
        from slack_sdk.socket_mode.request import SocketModeRequest
        from slack_sdk.socket_mode.response import SocketModeResponse

        self._web_client = AsyncWebClient(token=self.bot_token)

        try:
            auth = await self._web_client.auth_test()
            self._bot_user_id = auth.get("user_id")
        except Exception as e:
            logger.warning("Slack auth_test failed: %s", e)
            return

        async def _handler(sm_client: SocketModeClient, req: SocketModeRequest) -> None:
            await sm_client.send_socket_mode_response(
                SocketModeResponse(envelope_id=req.envelope_id)
            )
            try:
                await self._process_event_payload(req.payload)
            except Exception as exc:
                logger.warning("Slack event handler error: %s", exc)

        while True:
            sm_client = SocketModeClient(
                app_token=self.app_token,
                web_client=self._web_client,
            )
            sm_client.socket_mode_request_listeners.append(_handler)
            try:
                await sm_client.connect()
                logger.info("Slack Socket Mode connected as %s", self._bot_user_id)
                while True:
                    await asyncio.sleep(1)
            except asyncio.CancelledError:
                try:
                    await sm_client.disconnect()
                except Exception:
                    pass
                raise
            except Exception as e:
                logger.warning("Slack Socket Mode error: %s — reconnecting in 5s", e)
                await asyncio.sleep(5)
