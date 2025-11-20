import time
import asyncio
from aiogram import BaseMiddleware
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery, Message
from aiogram.exceptions import TelegramBadRequest
from models import User
from config import Config

class SubscriptionMiddleware(BaseMiddleware):
    def __init__(self):
        super().__init__()
        self._last_ts = {}            # user_id -> last handled monotonic time
        self._lock = asyncio.Lock()
        self._interval = 1.0         # seconds
        self._auto_delete_secs = 3.0 # message will be auto-deleted after this many seconds for Message-type alerts

    async def _send_message_and_delete(self, bot, chat_id: int, text: str):
        """
        Send a short message and delete it after self._auto_delete_secs.
        Uses create_task so middleware doesn't block waiting for deletion.
        """
        try:
            sent = await bot.send_message(chat_id=chat_id, text=text)
        except Exception:
            return
        async def _del_later(msg):
            await asyncio.sleep(self._auto_delete_secs)
            try:
                await bot.delete_message(chat_id=msg.chat.id, message_id=msg.message_id)
            except Exception:
                pass
        # schedule deletion but don't await
        asyncio.create_task(_del_later(sent))

    async def __call__(self, handler, event, data):
        user_obj = getattr(event, "from_user", None)
        bot = data.get("bot") or getattr(event, "bot", None)

        # if no user id (e.g., some system updates) — pass through
        if not (user_obj and getattr(user_obj, "id", None)):
            return await handler(event, data)

        tg_id = user_obj.id

        # RATE LIMIT check (1 request per self._interval seconds)
        now = time.monotonic()
        async with self._lock:
            last = self._last_ts.get(tg_id)
            if last is not None and (now - last) < self._interval:
                # Rate limit hit -> show alert depending on update type
                try:
                    # If it's a callback query -> show popup alert
                    if isinstance(event, CallbackQuery):
                        try:
                            await bot.answer_callback_query(
                                callback_query_id=event.id,
                                text="Iltimos — 1 soniyada faqat bitta amal bajariladi. Keyinroq urinib ko‘ring.",
                                show_alert=True
                            )
                        except Exception:
                            # best-effort: if answer fails, fallback to sending message
                            await self._send_message_and_delete(bot, tg_id, "Iltimos — 1 soniyada faqat bitta amal bajariladi. Keyinroq urinib ko‘ring.")
                    # If it's a normal message -> send ephemeral reply (auto-delete)
                    elif isinstance(event, Message):
                        # reply to the user's message so it appears near the message
                        try:
                            sent = await bot.send_message(chat_id=tg_id, text="Iltimos — 1 soniyada faqat bitta amal bajariladi. Keyinroq urinib ko‘ring.", reply_to_message_id=event.message_id)
                            # schedule deletion of our ephemeral message
                            async def _del_later(msg):
                                await asyncio.sleep(self._auto_delete_secs)
                                try:
                                    await bot.delete_message(chat_id=msg.chat.id, message_id=msg.message_id)
                                except Exception:
                                    pass
                            asyncio.create_task(_del_later(sent))
                        except Exception:
                            # fallback: try simple send+auto-delete
                            await self._send_message_and_delete(bot, tg_id, "Iltimos — 1 soniyada faqat bitta amal bajariladi. Keyinroq urinib ko‘ring.")
                    else:
                        # other update types: send simple message (best-effort)
                        await self._send_message_and_delete(bot, tg_id, "Iltimos — 1 soniyada faqat bitta amal bajariladi. Keyinroq urinib ko‘ring.")
                except Exception:
                    # swallow everything — do not call handler
                    pass

                # Do NOT call the handler for this update (rate-limited)
                return

            # accept this event and record timestamp
            self._last_ts[tg_id] = now
            # cleanup old entries occasionally
            if len(self._last_ts) > 10000:
                cutoff = now - 60
                to_del = [u for u, t in self._last_ts.items() if t < cutoff]
                for u in to_del:
                    del self._last_ts[u]

        # --- continue original logic (user create + subscription check) ---
        defaults = {
            "first_name": getattr(user_obj, "first_name", None),
            "last_name": getattr(user_obj, "last_name", None),
            "lang": getattr(user_obj, "language_code", "uz")
        }
        try:
            User.get_or_create(telegram_id=tg_id, defaults=defaults)
        except Exception:
            pass

        if not bot or not getattr(Config, "CHANNEL_ID", None):
            return await handler(event, data)

        try:
            member = await bot.get_chat_member(chat_id=Config.CHANNEL_ID, user_id=tg_id)
            if member.status in ("creator", "administrator", "member", "restricted"):
                return await handler(event, data)
        except TelegramBadRequest:
            pass
        except Exception:
            return await handler(event, data)

        kb_buttons = []
        chan_username = getattr(Config, "CHANNEL_USERNAME", None)
        if chan_username:
            kb_buttons.append(
                InlineKeyboardButton(text="Kanalga o‘tish", url=f"https://t.me/{chan_username}")
            )
        kb_buttons.append(InlineKeyboardButton(text="Obunani tekshirish", callback_data="check_sub"))

        markup = InlineKeyboardMarkup(inline_keyboard=[[b] for b in kb_buttons])

        try:
            await bot.send_message(
                chat_id=tg_id,
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