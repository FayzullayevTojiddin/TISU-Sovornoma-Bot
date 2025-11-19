from aiogram import BaseMiddleware
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.exceptions import TelegramBadRequest
from models import User
from config import Config

class SubscriptionMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        user_obj = getattr(event, "from_user", None)
        bot = data.get("bot") or getattr(event, "bot", None)
        if not (user_obj and getattr(user_obj, "id", None)):
            return await handler(event, data)

        tg_id = user_obj.id
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
                InlineKeyboardButton(text="Kanalga o‘tish", url=f"t.me/{chan_username}")
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

        return
