from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.types import CallbackQuery
from models import ConfidraMudiri, db, User
from peewee import fn, JOIN
from config import Config

from keyboards.inline_keyboards import (
    fakultet_tugmalari,
    mudir_tugmalari,
    get_fakultet_name_by_id,
    vote_keyboard,
    stats_keyboard,
    FAKULTETLAR
)

router = Router(name=__name__)

WELCOME_TEXT = (
    "<b>🎓 TISU So'rovnoma</b>\n\n"
    "<b>Iltimos, ovoz berish uchun kerakli fakultetni tanlang.</b>\n\n"
    "<b>Quyidagi ro'yxatdan boshlang — keyin kafedralar ro'yxati chiqadi.</b>"
)

@router.callback_query(F.data == "check_sub")
async def check_subscription(callback: CallbackQuery):
    bot = callback.message.bot
    user_id = callback.from_user.id

    try:
        member = await bot.get_chat_member(Config.CHANNEL_ID, user_id)
        is_subscribed = member.status in ("creator", "administrator", "member", "restricted")
    except Exception:
        is_subscribed = False

    if is_subscribed:
        await callback.answer("✔ Obuna tasdiqlandi!", show_alert=False)

        try:
            await callback.message.edit_text(
                WELCOME_TEXT,
                parse_mode="HTML",
                reply_markup=fakultet_tugmalari()
            )
        except:
            await callback.message.answer(
                WELCOME_TEXT,
                parse_mode="HTML",
                reply_markup=fakultet_tugmalari()
            )

        return

    await callback.answer("❗ Obuna topilmadi", show_alert=False)

    try:
        await callback.message.edit_text(
            "❌ <b>Siz hali kanalga obuna bo‘lmagansiz.</b>\n\n"
            "📢 Iltimos, rasmiy kanalga obuna bo‘ling va qayta tekshiring.",
            parse_mode="HTML",
            reply_markup=callback.message.reply_markup
        )
    except:
        await callback.message.answer(
            "❌ Siz hali kanalga obuna bo‘lmagansiz.\n\n"
            "📢 Iltimos, obuna bo‘ling va qayta tekshiring.",
            parse_mode="HTML",
            reply_markup=callback.message.reply_markup
        )

@router.message(Command("start"))
async def start_handler(message: types.Message):
    await message.answer(
        WELCOME_TEXT,
        reply_markup=fakultet_tugmalari(),
        parse_mode="HTML"
    )


@router.callback_query(lambda c: c.data and c.data.startswith("back_fakultet:"))
async def back_fakultet_handler(call: CallbackQuery):
    await call.message.answer(
        WELCOME_TEXT,
        reply_markup=fakultet_tugmalari(),
        parse_mode="HTML"
    )
    await call.message.delete()
    await call.answer()

@router.callback_query(lambda c: c.data and c.data.startswith("fakultet:"))
async def fakultet_callback(call: CallbackQuery):
    try:
        fid = int(call.data.split(":", 1)[1])
    except (IndexError, ValueError):
        await call.answer("Noto'g'ri ma'lumot.", show_alert=True)
        return

    fakultet_name = get_fakultet_name_by_id(fid) or "Tanlangan fakultet"
    await call.message.edit_text(
        f"🏛️ <b>{fakultet_name}</b>\n\n"
        "Quyidagi kafedralardan birini tanlang:",
        reply_markup=mudir_tugmalari(fid),
        parse_mode="HTML"
    )
    await call.answer()

@router.callback_query(lambda c: c.data and c.data.startswith("mudir:"))
async def mudir_detail(cb: CallbackQuery):
    try:
        _, mid = cb.data.split(":", 1)
        db.connect(reuse_if_open=True)
        mudir = ConfidraMudiri.get_or_none(ConfidraMudiri.id == int(mid))
        vote_button = vote_keyboard(mudir_id=mudir.id, facultet_id=mudir.facultet_type)
        if not mudir:
            await cb.answer("Nomzod topilmadi.", show_alert=True)
            return
        text = (
            f"🧑‍🏫 <b>{mudir.full_name}</b>\n"
            f"🏫 <b>Fakultet:</b> {FAKULTETLAR.get(mudir.facultet_type, mudir.facultet_type)}\n\n"
            f"📝 <b>Maʼlumot:</b>\n"
            f"{mudir.description or 'Hozircha izoh mavjud emas.'}"
        )
        if mudir.image:
            try:
                await cb.message.answer_photo(photo=mudir.image, caption=text, parse_mode="HTML", reply_markup=vote_button)
            except Exception:
                await cb.message.answer(text, parse_mode="HTML", reply_markup=vote_button)
        else:
            await cb.message.answer(text, parse_mode="HTML", reply_markup=vote_button)
        await cb.answer()
        await cb.message.delete()
    except Exception:
        await cb.answer("Xatolik yuz berdi.", show_alert=True)

@router.callback_query(lambda c: c.data == "main_menu")
async def main_menu_handler(call: CallbackQuery):
    await call.message.edit_text(
        WELCOME_TEXT,
        reply_markup=fakultet_tugmalari(),
        parse_mode="HTML"
    )
    await call.answer()


@router.callback_query(lambda c: c.data and c.data.startswith("vote:"))
async def vote_handler(call: CallbackQuery):
    try:
        mudir_id = int(call.data.split(":", 1)[1])
    except (IndexError, ValueError):
        await call.answer("Noto'g'ri ma'lumot.", show_alert=True)
        return

    db.connect(reuse_if_open=True)
    mudir = ConfidraMudiri.get_or_none(ConfidraMudiri.id == mudir_id)
    if not mudir:
        await call.answer("Nomzod topilmadi.", show_alert=True)
        return

    tg_id = call.from_user.id
    user = User.get_or_none(User.telegram_id == tg_id)

    if not user:
        user = User.create(
            telegram_id=tg_id,
            first_name=call.from_user.first_name,
            last_name=call.from_user.last_name,
            lang=call.from_user.language_code or "uz"
        )

    if user.confedra_mudiri_id:
        await call.answer("Siz allaqachon ovoz bergansiz.", show_alert=True)
        return

    user.confedra_mudiri = mudir.id
    user.save()

    text = f"🎉 Siz <b>{mudir.full_name}</b> uchun ovoz berdingiz. Rahmat!"
    markup = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [types.InlineKeyboardButton(text="🏠 Asosiy menyu", callback_data="main_menu")]
        ]
    )

    try:
        await call.message.delete()
    except Exception:
        pass

    await call.message.answer(
        text,
        parse_mode="HTML",
        reply_markup=markup
    )

    await call.answer("Ovoz qabul qilindi ✅")

@router.callback_query(lambda c: c.data == "stats")
async def stats_handler(cb: CallbackQuery):
    db.connect(reuse_if_open=True)

    q = (
        ConfidraMudiri
        .select(
            ConfidraMudiri,
            fn.COUNT(User.id).alias("votes_count")
        )
        .join(User, JOIN.LEFT_OUTER, on=(User.confedra_mudiri == ConfidraMudiri.id))
        .group_by(ConfidraMudiri.id)
        .order_by(fn.COUNT(User.id).desc())
    )

    lines = ["📊 <b>Ovozlar Statistikasi</b>\n"]

    rank = 1
    for r in q:
        count = r.votes_count or 0
        lines.append(f"{rank}. {r.full_name} — <b>{count}</b> ta")
        rank += 1

    text = "\n".join(lines)

    await cb.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=stats_keyboard()
    )
    await cb.answer()