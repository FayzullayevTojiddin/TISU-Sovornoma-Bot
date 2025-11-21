import time
import asyncio
import logging
from collections import deque
from typing import Optional

from aiogram import BaseMiddleware
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery, Message
from aiogram.exceptions import TelegramBadRequest

from models import User
from config import Config

LOG = logging.getLogger(__name__)


class SubscriptionMiddleware(BaseMiddleware):
    def __init__(self):
        super().__init__()
        # user_id -> deque of monotonic timestamps (requests within sliding window)
        self._req_times: dict[int, deque] = {}
        # user_id -> blocked_until monotonic time (float) if blocked, else absent
        self._blocked_until: dict[int, float] = {}
        # avoid spamming the "please subscribe" prompt: user_id -> last prompt monotonic time
        self._last_sub_prompt: dict[int, float] = {}

        self._lock = asyncio.Lock()

        # config
        self._window_secs = 20.0         # sliding window length
        self._limit_count = 20           # if >= this many in window -> block
        self._block_secs = 60.0          # block duration when exceeded
        self._sub_prompt_cooldown = 30.0 # don't re-send sub prompt more often than this
        self._auto_delete_secs = 3.0     # ephemeral text messages auto-delete

    async def _send_message_and_delete(self, bot, chat_id: int, text: str, reply_to: Optional[int] = None):
        try:
            if reply_to:
                sent = await bot.send_message(chat_id=chat_id, text=text, reply_to_message_id=reply_to)
            else:
                sent = await bot.send_message(chat_id=chat_id, text=text)
        except Exception as e:
            LOG.debug("Failed to send rate-limit message: %s", e)
            return

        async def _del_later(msg):
            await asyncio.sleep(self._auto_delete_secs)
            try:
                await bot.delete_message(chat_id=msg.chat.id, message_id=msg.message_id)
            except Exception:
                pass

        asyncio.create_task(_del_later(sent))

    def _extract_user_and_type(self, event):
        """
        Returns tuple (user_id, kind, message_id, callback_obj)
        kind: "message" / "callback" / "other"
        callback_obj: actual CallbackQuery object if available, else None
        """
        if isinstance(event, CallbackQuery):
            user = getattr(event.from_user, "id", None)
            return user, "callback", None, event

        if isinstance(event, Message):
            user = getattr(event.from_user, "id", None)
            return user, "message", getattr(event, "message_id", None), None

        if hasattr(event, "callback_query") and event.callback_query:
            user = getattr(event.callback_query.from_user, "id", None)
            return user, "callback", None, event.callback_query
        if hasattr(event, "message") and event.message:
            user = getattr(event.message.from_user, "id", None)
            return user, "message", getattr(event.message, "message_id", None), None

        user = getattr(getattr(event, "from_user", None), "id", None)
        return user, "other", None, None

    async def __call__(self, handler, event, data):
        bot = data.get("bot") or getattr(event, "bot", None)
        user_id, kind, msg_id, cq = self._extract_user_and_type(event)

        if not user_id:
            # no user -> just continue
            return await handler(event, data)

        now = time.monotonic()

        # --- Rate limiting & blocking logic (atomic) ---
        async with self._lock:
            # check if currently blocked
            blocked_until = self._blocked_until.get(user_id)
            if blocked_until and now < blocked_until:
                LOG.debug("User %s is currently blocked until %s (now=%s)", user_id, blocked_until, now)
                # notify user about block (do not call handler)
                try:
                    remaining = int(blocked_until - now)
                    msg = f"Siz juda koʻp soʻrov yubordingiz. {remaining} soniyaga bloklandi. Iltimos, keyinroq urinib koʻring."
                    # prefer callback answer
                    if kind == "callback":
                        try:
                            if cq is not None:
                                await cq.answer(text=msg, show_alert=True)
                                return
                            else:
                                cbid = getattr(event, "id", None) or getattr(getattr(event, "callback_query", None), "id", None)
                                if cbid:
                                    await bot.answer_callback_query(callback_query_id=cbid, text=msg, show_alert=True)
                                    return
                        except Exception as e:
                            LOG.debug("callback answer failed while blocked: %s", e)
                            await self._send_message_and_delete(bot, user_id, msg)
                            return
                    else:
                        await self._send_message_and_delete(bot, user_id, msg, reply_to=msg_id)
                        return
                except Exception as e:
                    LOG.debug("Failed to notify blocked user %s: %s", user_id, e)
                    return

            # not currently blocked -> update request timestamps
            dq = self._req_times.get(user_id)
            if dq is None:
                dq = deque()
                self._req_times[user_id] = dq

            # push current timestamp and pop older than window
            dq.append(now)
            cutoff = now - self._window_secs
            while dq and dq[0] < cutoff:
                dq.popleft()

            # if limit reached -> block
            if len(dq) >= self._limit_count:
                self._blocked_until[user_id] = now + self._block_secs
                # clear request history to avoid repeated triggers
                dq.clear()
                LOG.info("User %s exceeded %d requests in %ds: blocking for %ds", user_id, self._limit_count, int(self._window_secs), int(self._block_secs))
                # inform user about the block
                try:
                    block_msg = f"Siz {int(self._window_secs)} soniyada {self._limit_count} yoki undan koʻp soʻrov yubordingiz. {int(self._block_secs)} soniyaga bloklanildi."
                    if kind == "callback":
                        try:
                            if cq is not None:
                                await cq.answer(text=block_msg, show_alert=True)
                                return
                            else:
                                cbid = getattr(event, "id", None) or getattr(getattr(event, "callback_query", None), "id", None)
                                if cbid:
                                    await bot.answer_callback_query(callback_query_id=cbid, text=block_msg, show_alert=True)
                                    return
                        except Exception as e:
                            LOG.debug("callback block answer failed: %s", e)
                            await self._send_message_and_delete(bot, user_id, block_msg)
                            return
                    else:
                        await self._send_message_and_delete(bot, user_id, block_msg, reply_to=msg_id)
                        return
                except Exception as e:
                    LOG.debug("Failed to notify user about new block: %s", e)
                    return

        # --- End rate-limit/block section ---

        # Record (or create) user in DB (non-critical; ignore failures)
        user_obj = getattr(event, "from_user", None) or getattr(getattr(event, "message", None), "from_user", None) or getattr(getattr(event, "callback_query", None), "from_user", None)
        defaults = {
            "first_name": getattr(user_obj, "first_name", None),
            "last_name": getattr(user_obj, "last_name", None),
            "lang": getattr(user_obj, "language_code", "uz")
        }
        try:
            User.get_or_create(telegram_id=user_id, defaults=defaults)
        except Exception:
            pass

        # If no bot or no channel configured, continue
        if not bot or not getattr(Config, "CHANNEL_ID", None):
            return await handler(event, data)

        # Check subscription. If not subscribed, send subscription prompt and DO NOT call handler.
        try:
            member = await bot.get_chat_member(chat_id=Config.CHANNEL_ID, user_id=user_id)
            if member.status in ("creator", "administrator", "member", "restricted"):
                # subscribed -> continue to handler
                return await handler(event, data)
        except TelegramBadRequest:
            # user is not a member or Telegram returned 400-series error -> treat as not subscribed
            pass
        except Exception as e:
            LOG.debug("Error while checking chat member for user %s: %s", user_id, e)
            # to be safe, allow handler to proceed on unexpected errors
            return await handler(event, data)

        # At this point: user is not subscribed -> send subscription prompt (but respect cooldown)
        last_prompt = self._last_sub_prompt.get(user_id, 0.0)
        if now - last_prompt < self._sub_prompt_cooldown:
            # recently prompted -> do not spam user again, and do not call handler
            LOG.debug("Skipping repeated sub prompt for user %s (cooldown)", user_id)
            return  # do not call handler

        # build keyboard and send message
        kb_buttons = []
        chan_username = getattr(Config, "CHANNEL_USERNAME", None)
        if chan_username:
            kb_buttons.append(InlineKeyboardButton(text="Kanalga o‘tish", url=f"https://t.me/{chan_username}"))
        kb_buttons.append(InlineKeyboardButton(text="Obunani tekshirish", callback_data="check_sub"))
        markup = InlineKeyboardMarkup(inline_keyboard=[[b] for b in kb_buttons])

        try:
            await bot.send_message(
                chat_id=user_id,
                text=(
                    "📢 <b>Botdan foydalanish uchun</b> bizning rasmiy kanalga obuna bo‘ling!\n\n"
                    "👉 Obuna bo‘lgach, pastdagi <b>“Obunani tekshirish”</b> tugmasini bosing.\n\n"
                    "❤️ Sizning qo‘llab-quvvatlashingiz biz uchun muhim!"
                ),
                parse_mode="HTML",
                reply_markup=markup
            )
        except Exception as e:
            LOG.debug("Failed to send subscription prompt to user %s: %s", user_id, e)

        # remember we prompted the user (to avoid spamming)
        self._last_sub_prompt[user_id] = now

        # important: DO NOT call handler when user is not subscribed
        return