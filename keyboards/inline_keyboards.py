from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton
from models import ConfidraMudiri, db

FAKULTETLAR = {
    1: "Iqtisodiyot va axborot texnologiyalari fakulteti",
    2: "Pedagogika va ijtimoiy-gumanitar fanlar fakulteti",
    3: "Tibbiyot fakulteti",
}

def fakultet_tugmalari():
    """
    Inline markup: har bir tugma callback_data: 'fakultet:<id>'
    """
    kb = InlineKeyboardBuilder()
    for fid, name in FAKULTETLAR.items():
        kb.add(
            InlineKeyboardButton(
                text=name,
                callback_data=f"fakultet:{fid}"
            )
        )
    
    kb.add(
        InlineKeyboardButton(
            text="📊 Statistika",
            callback_data="stats"
        )
    )
    kb.adjust(1)
    return kb.as_markup()

def mudir_tugmalari(fakultet_id: int):
    db.connect(reuse_if_open=True)
    rows = ConfidraMudiri.select().where(ConfidraMudiri.facultet_type == fakultet_id).order_by(ConfidraMudiri.full_name)
    kb = InlineKeyboardBuilder()
    for r in rows:
        try:
            votes = r.votes.count()
        except Exception:
            votes = 0
        name = r.full_name
        if len(name) > 18:
            name = name[:15] + "..."
        kb.add(InlineKeyboardButton(text=f"{name} ({votes})", callback_data=f"mudir:{r.id}"))
    kb.add(InlineKeyboardButton(text="🏠 Asosiy menyu", callback_data="main_menu"))
    kb.adjust(1)
    return kb.as_markup()

def vote_keyboard(mudir_id: int, facultet_id: int):
    kb = InlineKeyboardBuilder()
    kb.add(InlineKeyboardButton(text="🗳 Ovoz berish", callback_data=f"vote:{mudir_id}"))
    kb.add(InlineKeyboardButton(text="⬅️ Orqaga", callback_data=f"back_fakultet:{facultet_id}"))
    kb.adjust(1)
    return kb.as_markup()

def get_fakultet_name_by_id(fid: int) -> str | None:
    return FAKULTETLAR.get(fid)

def stats_keyboard():
    kb = InlineKeyboardBuilder()
    kb.add(
        InlineKeyboardButton(
            text="🏠 Bosh sahifa",
            callback_data="main_menu"
        )
    )
    kb.adjust(1)
    return kb.as_markup()