from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy import select
from database import AsyncSessionLocal, PaymentLink


def admin_main_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📅 Изменить даты уроков", callback_data="admin_edit_slots")],
        [InlineKeyboardButton(text="💳 Редактировать способы оплаты", callback_data="admin_payment")],
        [InlineKeyboardButton(text="📋 Ожидающие подтверждения", callback_data="admin_bookings")],
        [InlineKeyboardButton(text="🚪 Выйти из аккаунта", callback_data="admin_logout")],
    ])


async def payment_links_menu() -> InlineKeyboardMarkup:
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(PaymentLink).where(PaymentLink.is_active == True))
        links = result.scalars().all()

    buttons = []
    for link in links:
        buttons.append([
            InlineKeyboardButton(text=f"🗑 {link.title}", callback_data=f"del_payment:{link.id}")
        ])
    buttons.append([InlineKeyboardButton(text="➕ Добавить ссылку", callback_data="add_payment_link")])
    buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data="admin_back")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def booking_approval_kb(booking_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"approve_booking:{booking_id}"),
            InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject_booking:{booking_id}"),
        ]
    ])
