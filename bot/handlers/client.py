import os
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from sqlalchemy import select
from database import AsyncSessionLocal, Booking, AvailableSlot, PaymentLink
from bot.keyboards.client_kb import client_main_menu
from datetime import datetime, timedelta

router = Router()

ADMIN_TELEGRAM_ID = int(os.getenv("ADMIN_TELEGRAM_ID", "0"))


async def send_client_menu(message: Message):
    await message.answer(
        "👋 <b>Привет!</b>\n\nЯ помогу вам записаться на урок. Выберите действие:",
        reply_markup=client_main_menu(),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "client_my_lessons")
async def client_my_lessons(callback: CallbackQuery):
    now = datetime.utcnow()
    week_ago = now - timedelta(weeks=1)
    week_ahead = now + timedelta(weeks=1)

    async with AsyncSessionLocal() as db:
        bookings = (await db.execute(
            select(Booking).where(
                Booking.student_telegram_id == callback.from_user.id,
                Booking.slot_datetime >= week_ago,
                Booking.slot_datetime <= week_ahead,
                Booking.status != "rejected"
            ).order_by(Booking.slot_datetime)
        )).scalars().all()

    if not bookings:
        await callback.message.answer(
            "📋 <b>Ваши уроки за ±1 неделю</b>\n\nУ вас нет записей на эту неделю.",
            parse_mode="HTML", reply_markup=client_main_menu()
        )
    else:
        status_emoji = {"pending": "⏳", "approved": "✅", "rejected": "❌"}
        status_text = {"pending": "Ожидает подтверждения", "approved": "Подтверждён", "rejected": "Отклонён"}
        text = "📋 <b>Ваши уроки за ±1 неделю:</b>\n\n"
        for b in bookings:
            emoji = status_emoji.get(b.status, "❓")
            st = status_text.get(b.status, b.status)
            dt_str = b.slot_datetime.strftime("%d.%m.%Y в %H:%M")
            text += f"{emoji} <b>{dt_str}</b> — {st}\n"
        await callback.message.answer(text, parse_mode="HTML", reply_markup=client_main_menu())
    await callback.answer()


@router.callback_query(F.data == "client_payment")
async def client_payment(callback: CallbackQuery):
    async with AsyncSessionLocal() as db:
        links = (await db.execute(
            select(PaymentLink).where(PaymentLink.is_active == True)
        )).scalars().all()

    if not links:
        await callback.message.answer(
            "💳 Ссылки на оплату пока не добавлены.\nСвяжитесь с учителем напрямую.",
            reply_markup=client_main_menu()
        )
    else:
        text = "💳 <b>Способы оплаты:</b>\n\n"
        for link in links:
            text += f"• <a href='{link.url}'>{link.title}</a>\n"
        text += "\n⚠️ <b>Важно:</b> при оплате обязательно укажите в примечании к платежу, за какие даты урока вы платите."
        await callback.message.answer(text, parse_mode="HTML", reply_markup=client_main_menu())
    await callback.answer()
