import time
import asyncio
import logging
from aiogram import BaseMiddleware
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery, Message
from aiogram.exceptions import TelegramBadRequest
from models import User
from config import Config

LOG = logging.getLogger(__name__)

class SubscriptionMiddleware(BaseMiddleware):
    def __init__(self):
        super().__init__()
        self._last_ts = {}            # user_id -> last handled monotonic time
        self._lock = asyncio.Lock()
        self._interval = 1.0         # seconds
        self._auto_delete_secs = 3.0

    async def _send_message_and_delete(self, bot, chat_id: int, text: str, reply_to: int | None = None):
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
        # Direct CallbackQuery object
        if isinstance(event, CallbackQuery):
            user = getattr(event.from_user, "id", None)
            return user, "callback", None, event

        # Direct Message object
        if isinstance(event, Message):
            user = getattr(event.from_user, "id", None)
            return user, "message", getattr(event, "message_id", None), None

        # Raw Update-like object with attributes
        if hasattr(event, "callback_query") and event.callback_query:
            user = getattr(event.callback_query.from_user, "id", None)
            return user, "callback", None, event.callback_query
        if hasattr(event, "message") and event.message:
            user = getattr(event.message.from_user, "id", None)
            return user, "message", getattr(event.message, "message_id", None), None

        # fallback
        user = getattr(getattr(event, "from_user", None), "id", None)
        return user, "other", None, None

    async def __call__(self, handler, event, data):
        bot = data.get("bot") or getattr(event, "bot", None)
        user_id, kind, msg_id, cq = self._extract_user_and_type(event)

        if not user_id:
            # no user -> just continue
            return await handler(event, data)

        # RATE LIMIT
        now = time.monotonic()
        async with self._lock:
            last = self._last_ts.get(user_id)
            if last is not None and (now - last) < self._interval:
                LOG.debug("Rate limit hit for user %s (kind=%s). last=%s now=%s", user_id, kind, last, now)
                # notify user: prefer CallbackQuery.answer() if available
                try:
                    if kind == "callback":
                        # prefer direct cq.answer()
                        if cq is not None:
                            try:
                                await cq.answer(
                                    text="Iltimos — 1 soniyada faqat bitta amal bajariladi. Keyinroq urinib ko‘ring.",
                                    show_alert=True
                                )
                                LOG.debug("Answered callback_query via cq.answer for user %s", user_id)
                            except Exception as e:
                                LOG.debug("cq.answer failed: %s", e)
                                # fallback to bot.answer_callback_query using id if available
                                try:
                                    callback_id = getattr(cq, "id", None)
                                    if callback_id:
                                        await bot.answer_callback_query(
                                            callback_query_id=callback_id,
                                            text="Iltimos — 1 soniyada faqat bitta amal bajariladi. Keyinroq urinib ko‘ring.",
                                            show_alert=True
                                        )
                                        LOG.debug("Answered callback_query via bot.answer_callback_query (fallback) for user %s", user_id)
                                    else:
                                        # final fallback: ephemeral message
                                        await self._send_message_and_delete(bot, user_id, "Iltimos — 1 soniyada faqat bitta amal bajariladi.")
                                except Exception as e2:
                                    LOG.debug("bot.answer_callback_query fallback failed: %s", e2)
                                    await self._send_message_and_delete(bot, user_id, "Iltimos — 1 soniyada faqat bitta amal bajariladi.")
                        else:
                            # no cq object available — try best-effort using bot
                            try:
                                callback_id = getattr(event, "id", None) or getattr(event, "callback_query", None) and getattr(event.callback_query, "id", None)
                                if callback_id:
                                    await bot.answer_callback_query(
                                        callback_query_id=callback_id,
                                        text="Iltimos — 1 soniyada faqat bitta amal bajariladi. Keyinroq urinib ko‘ring.",
                                        show_alert=True
                                    )
                                    LOG.debug("Answered callback_query via bot.answer_callback_query (event fallback) for user %s", user_id)
                                else:
                                    await self._send_message_and_delete(bot, user_id, "Iltimos — 1 soniyada faqat bitta amal bajariladi.")
                            except Exception as e:
                                LOG.debug("Fallback bot.answer_callback_query failed: %s", e)
                                await self._send_message_and_delete(bot, user_id, "Iltimos — 1 soniyada faqat bitta amal bajariladi.")
                    elif kind == "message":
                        await self._send_message_and_delete(bot, user_id, "Iltimos — 1 soniyada faqat bitta amal bajariladi. Keyinroq urinib ko‘ring.", reply_to=msg_id)
                    else:
                        await self._send_message_and_delete(bot, user_id, "Iltimos — 1 soniyada faqat bitta amal bajariladi.")
                except Exception as e:
                    LOG.debug("Failed to notify user about rate limit: %s", e)

                return  # DO NOT call handler

            # accept and record
            self._last_ts[user_id] = now
            if len(self._last_ts) > 10000:
                cutoff = now - 60
                to_del = [u for u, t in self._last_ts.items() if t < cutoff]
                for u in to_del:
                    del self._last_ts[u]

        # continue original logic (User.get_or_create + subscription check)
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

        if not bot or not getattr(Config, "CHANNEL_ID", None):
            return await handler(event, data)

        try:
            member = await bot.get_chat_member(chat_id=Config.CHANNEL_ID, user_id=user_id)
            if member.status in ("creator", "administrator", "member", "restricted"):
                return await handler(event, data)
        except TelegramBadRequest:
            pass
        except Exception:
            return await handler(event, data)

        # send subscription message
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
        except Exception:
            pass

        return await handler(event, data)
