# backend/telegram.py
"""Telegram bot integration — polling loop, message routing, review item approval."""
import asyncio
import logging
import mimetypes
import re
from typing import Callable, Awaitable

import httpx

logger = logging.getLogger(__name__)


def _parse_product_id(text: str, products: list[dict]) -> tuple[str | None, str]:
    """
    Parse 'for <product-name>: <message>' prefix (case-insensitive, fuzzy).
    Returns (product_id, message). product_id is None if no prefix or no match.
    If no match, the original text is returned unchanged.
    """
    m = re.match(r"(?i)^for\s+(.+?):\s*(.+)$", text.strip(), re.DOTALL)
    if not m:
        return None, text.strip()

    name_fragment = m.group(1).strip().lower()
    message = m.group(2).strip()

    for product in products:
        if name_fragment in product["name"].lower():
            return product["id"], message

    # No product matched — return original text unchanged so caller can handle it
    return None, text.strip()


class TelegramBot:
    def __init__(
        self,
        token: str,
        chat_id: str,
        directive_callback: Callable[[str, str], Awaitable[None]],
        products_fn: Callable[[], list[dict]],
        last_active_product_fn: Callable[[], str],
        resolve_review_fn: Callable[[int, str], None],
        broadcast_fn: Callable[[dict], Awaitable[None]],
    ):
        self.token = token
        self.chat_id = str(chat_id)
        self._directive_callback = directive_callback
        self._products_fn = products_fn
        self._last_active_product_fn = last_active_product_fn
        self.resolve_review_fn = resolve_review_fn
        self.broadcast_fn = broadcast_fn
        self._offset = 0
        self._pending_products: set[str] = set()
        self._review_message_ids: dict[int, int] = {}

    def _url(self, method: str) -> str:
        return f"https://api.telegram.org/bot{self.token}/{method}"

    async def send_message(self, text: str, reply_markup: dict | None = None) -> int | None:
        """Send a message to TELEGRAM_CHAT_ID. Returns message_id or None."""
        payload: dict = {"chat_id": self.chat_id, "text": text, "parse_mode": "HTML"}
        if reply_markup is not None:
            payload["reply_markup"] = reply_markup
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(self._url("sendMessage"), json=payload)
                data = resp.json()
                if data.get("ok"):
                    return data["result"]["message_id"]
        except Exception as e:
            logger.warning("Telegram sendMessage failed: %s", e)
        return None

    async def send_typing(self) -> None:
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                await client.post(self._url("sendChatAction"), json={
                    "chat_id": self.chat_id,
                    "action": "typing",
                })
        except Exception:
            pass

    async def edit_message(self, message_id: int, text: str) -> None:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                await client.post(self._url("editMessageText"), json={
                    "chat_id": self.chat_id,
                    "message_id": message_id,
                    "text": text,
                    "parse_mode": "HTML",
                })
        except Exception as e:
            logger.warning("Telegram editMessageText failed: %s", e)

    async def answer_callback(self, callback_query_id: str) -> None:
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                await client.post(self._url("answerCallbackQuery"), json={
                    "callback_query_id": callback_query_id,
                })
        except Exception:
            pass

    async def get_me(self) -> dict | None:
        """Fetch bot info for status checks. Returns result dict or None."""
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(self._url("getMe"))
                data = resp.json()
                return data.get("result") if data.get("ok") else None
        except Exception:
            return None

    async def _download_telegram_file(self, file_id: str) -> tuple[str, str]:
        """Download a Telegram file by file_id. Returns (local_path, mime_type)."""
        from backend.uploads import save_uploaded_file

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(self._url("getFile"), params={"file_id": file_id})
                data = resp.json()
                if not data.get("ok"):
                    raise ValueError(f"getFile failed: {data}")
                file_path = data["result"]["file_path"]

            download_url = f"https://api.telegram.org/file/bot{self.token}/{file_path}"
            async with httpx.AsyncClient(timeout=60) as client:
                resp = await client.get(download_url)
                resp.raise_for_status()
                raw = resp.content

            original_name = file_path.split("/")[-1]
            mime = mimetypes.guess_type(original_name)[0] or "application/octet-stream"
            local_path = save_uploaded_file(original_name, raw)
            return str(local_path), mime

        except Exception as e:
            logger.warning("Failed to download Telegram file %s: %s", file_id, e)
            raise

    async def send_document(self, file_path: str) -> None:
        """Send a file as a Telegram document to TELEGRAM_CHAT_ID."""
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                with open(file_path, "rb") as f:
                    await client.post(
                        self._url("sendDocument"),
                        data={"chat_id": self.chat_id},
                        files={"document": f},
                    )
        except Exception as e:
            logger.warning("Telegram sendDocument failed: %s", e)

    async def send_video(self, file_path: str) -> None:
        """Send a video via Telegram. Falls back to sendDocument for files over 50 MB."""
        try:
            from pathlib import Path as _Path
            size = _Path(file_path).stat().st_size
            if size > 50 * 1024 * 1024:
                await self.send_document(file_path)
                return
            async with httpx.AsyncClient(timeout=120) as client:
                with open(file_path, "rb") as f:
                    await client.post(
                        self._url("sendVideo"),
                        data={"chat_id": self.chat_id},
                        files={"video": f},
                    )
        except Exception as e:
            logger.warning("Telegram sendVideo failed: %s", e)

    async def notify(self, event: dict) -> None:
        """Forward relevant backend events to Telegram."""
        event_type = event.get("type")
        product_id = event.get("product_id", "")

        if event_type == "agent_done":
            if product_id in self._pending_products:
                self._pending_products.discard(product_id)
                content = event.get("content", "")
                if content:
                    await self.send_message(content)

        elif event_type == "activity_done":
            summary = event.get("summary", "")
            if summary:
                await self.send_message(f"✅ Agent finished: {summary[:400]}")

        elif event_type == "review_item_added":
            item = event.get("item", {})
            await self._send_review_item(item)

    async def _send_review_item(self, item: dict) -> None:
        item_id = item.get("id")
        title = item.get("title", "Review item")
        description = item.get("description", "")
        risk_label = item.get("risk_label", "")

        text = f"📋 <b>Review Required</b>\n\n<b>{title}</b>\n\n"
        if risk_label:
            text += f"⚠️ {risk_label}\n\n"
        if description:
            text += description

        if len(text) > 4000:
            text = text[:4000] + "\n…"

        reply_markup = {
            "inline_keyboard": [[
                {"text": "✅ Approve", "callback_data": f"approve:{item_id}"},
                {"text": "❌ Reject",  "callback_data": f"reject:{item_id}"},
            ]]
        }
        msg_id = await self.send_message(text, reply_markup=reply_markup)
        if msg_id and item_id is not None:
            self._review_message_ids[item_id] = msg_id

    async def _handle_message(self, message: dict) -> None:
        from_id = str(message.get("from", {}).get("id", ""))
        if from_id != self.chat_id:
            return

        text = (message.get("text") or message.get("caption") or "").strip()

        # Detect file attachments
        file_ref: str | None = None
        file_id: str | None = None

        if "video" in message:
            file_id = message["video"].get("file_id")
        elif "document" in message:
            file_id = message["document"].get("file_id")
        elif "photo" in message:
            # photos come as array — take highest resolution (last item)
            photos = message["photo"]
            if photos:
                file_id = photos[-1].get("file_id")

        if file_id:
            try:
                local_path, mime = await self._download_telegram_file(file_id)
                file_ref = f"[Attached file: {local_path} ({mime})]"
            except Exception:
                pass  # warning already logged inside _download_telegram_file

        if not text and not file_ref:
            return

        # Build directive text — file reference first, then user text
        parts = [p for p in [file_ref, text] if p]
        directive_text = "\n\n".join(parts)

        products = self._products_fn()
        product_id, clean_text = _parse_product_id(directive_text, products)
        if product_id is None:
            product_id = self._last_active_product_fn()

        known_ids = {p["id"] for p in products}
        if product_id not in known_ids:
            names = ", ".join(p["name"] for p in products[:3])
            await self.send_message(f"Unknown product. Try: for {names.split(',')[0]}: &lt;message&gt;")
            return

        self._pending_products.add(product_id)
        await self.send_typing()
        await self._directive_callback(product_id, clean_text)

    async def _handle_callback(self, callback_query: dict) -> None:
        from_id = str(callback_query.get("from", {}).get("id", ""))
        await self.answer_callback(callback_query["id"])

        if from_id != self.chat_id:
            return

        data = callback_query.get("data", "")
        message_id = callback_query.get("message", {}).get("message_id")

        if ":" not in data:
            return
        action_str, item_id_str = data.split(":", 1)
        try:
            item_id = int(item_id_str)
        except ValueError:
            return

        if action_str == "approve":
            self.resolve_review_fn(item_id, "approved")
            await self.broadcast_fn({"type": "review_resolved", "review_item_id": item_id, "action": "approved"})
            if message_id:
                await self.edit_message(message_id, "✅ Approved")
        elif action_str == "reject":
            self.resolve_review_fn(item_id, "skipped")
            await self.broadcast_fn({"type": "review_resolved", "review_item_id": item_id, "action": "skipped"})
            if message_id:
                await self.edit_message(message_id, "❌ Rejected")

    async def start(self) -> None:
        """Long-poll for updates. Exits immediately if token or chat_id is unset."""
        if not self.token or not self.chat_id:
            logger.info("Telegram not configured — polling disabled")
            return
        logger.info("Telegram polling started")
        while True:
            try:
                async with httpx.AsyncClient(timeout=35) as client:
                    resp = await client.get(self._url("getUpdates"), params={
                        "offset": self._offset,
                        "timeout": 30,
                        "allowed_updates": ["message", "callback_query"],
                    })
                    data = resp.json()
                    if not data.get("ok"):
                        await asyncio.sleep(5)
                        continue
                    for update in data.get("result", []):
                        self._offset = update["update_id"] + 1
                        if "message" in update:
                            await self._handle_message(update["message"])
                        elif "callback_query" in update:
                            await self._handle_callback(update["callback_query"])
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.warning("Telegram polling error: %s", e)
                await asyncio.sleep(5)
