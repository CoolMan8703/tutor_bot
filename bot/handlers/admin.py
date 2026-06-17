import os
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from sqlalchemy import select, delete
from database import AsyncSessionLocal, AdminSession, PaymentLink, Booking, AvailableSlot
from bot.keyboards.admin_kb import booking_approval_kb, payment_links_menu
from bot.keyboards.client_kb import admin_main_menu_with_webapp, client_main_menu

router = Router()
def student_label(username, name):
    if username:
        return f"@{username}"
    if name:
        return name
    return "Неизвестно"
    
ADMIN_LOGIN = os.getenv("ADMIN_LOGIN", "teacher")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "password")
ADMIN_TELEGRAM_ID = int(os.getenv("ADMIN_TELEGRAM_ID", "0"))


def role_selection_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👨‍🏫 Я — учитель", callback_data="role_teacher")],
        [InlineKeyboardButton(text="👨‍🎓 Я — ученик", callback_data="role_student")],
    ])


async def is_admin_authenticated(telegram_id: int) -> bool:
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(AdminSession).where(
                AdminSession.telegram_id == telegram_id,
                AdminSession.is_authenticated == True
            )
        )
        return result.scalar_one_or_none() is not None


async def get_admin_session(telegram_id: int):
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(AdminSession).where(AdminSession.telegram_id == telegram_id)
        )
        return result.scalar_one_or_none()


@router.message(Command("start"))
async def cmd_start(message: Message):
    if message.from_user.id == ADMIN_TELEGRAM_ID:
        if await is_admin_authenticated(message.from_user.id):
            await message.answer(
                "👨‍🏫 <b>Панель учителя</b>\n\nВыберите действие:",
                reply_markup=admin_main_menu_with_webapp(),
                parse_mode="HTML"
            )
            return
    await message.answer(
        "👋 <b>Добро пожаловать!</b>\n\nКто вы?",
        reply_markup=role_selection_kb(),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "role_student")
async def role_student(callback: CallbackQuery):
    await callback.message.edit_text(
        "👨‍🎓 <b>Добро пожаловать!</b>\n\nВыберите действие:",
        parse_mode="HTML",
        reply_markup=client_main_menu()
    )
    await callback.answer()


@router.callback_query(F.data == "role_teacher")
async def role_teacher(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_TELEGRAM_ID:
        await callback.answer("❌ У вас нет доступа к панели учителя.", show_alert=True)
        return
    if await is_admin_authenticated(callback.from_user.id):
        await callback.message.edit_text(
            "👨‍🏫 <b>Панель учителя</b>\n\nВыберите действие:",
            parse_mode="HTML",
            reply_markup=admin_main_menu_with_webapp()
        )
    else:
        await callback.message.edit_text(
            "🔐 <b>Вход в панель учителя</b>\n\nВведите кодовое слово (логин):",
            parse_mode="HTML"
        )
        async with AsyncSessionLocal() as db:
            existing = (await db.execute(
                select(AdminSession).where(AdminSession.telegram_id == callback.from_user.id)
            )).scalar_one_or_none()
            if not existing:
                db.add(AdminSession(telegram_id=callback.from_user.id, login_step="waiting_login"))
            else:
                existing.login_step = "waiting_login"
                existing.is_authenticated = False
            await db.commit()
    await callback.answer()


@router.callback_query(F.data == "admin_logout")
async def admin_logout(callback: CallbackQuery):
    async with AsyncSessionLocal() as db:
        result = (await db.execute(
            select(AdminSession).where(AdminSession.telegram_id == callback.from_user.id)
        )).scalar_one_or_none()
        if result:
            result.is_authenticated = False
            result.login_step = "none"
        await db.commit()
    await callback.message.edit_text("🚪 <b>Вы вышли из панели учителя.</b>", parse_mode="HTML")
    await callback.message.answer("👋 Кто вы?", reply_markup=role_selection_kb())
    await callback.answer("Выход выполнен")


@router.message(F.text)
async def handle_text(message: Message):
    if message.from_user.id == ADMIN_TELEGRAM_ID:
        session = await get_admin_session(message.from_user.id)

        if session and session.login_step == "waiting_login":
            if message.text == ADMIN_LOGIN:
                async with AsyncSessionLocal() as db:
                    s = (await db.execute(select(AdminSession).where(AdminSession.telegram_id == message.from_user.id))).scalar_one_or_none()
                    if s: s.login_step = "waiting_password"
                    await db.commit()
                await message.answer("🔑 Введите пароль:")
            else:
                await message.answer("❌ Неверный логин. Попробуйте снова:")

        elif session and session.login_step == "waiting_password":
            if message.text == ADMIN_PASSWORD:
                async with AsyncSessionLocal() as db:
                    s = (await db.execute(select(AdminSession).where(AdminSession.telegram_id == message.from_user.id))).scalar_one_or_none()
                    if s: s.login_step = "none"; s.is_authenticated = True
                    await db.commit()
                await message.answer("✅ <b>Вход выполнен!</b>\n\nДобро пожаловать:", reply_markup=admin_main_menu_with_webapp(), parse_mode="HTML")
            else:
                await message.answer("❌ Неверный пароль. Попробуйте снова:")

        elif session and session.login_step == "waiting_payment_title":
            async with AsyncSessionLocal() as db:
                s = (await db.execute(select(AdminSession).where(AdminSession.telegram_id == message.from_user.id))).scalar_one_or_none()
                if s: s.login_step = f"waiting_payment_url:{message.text}"
                await db.commit()
            await message.answer("🔗 Теперь введите URL ссылки на оплату:")

        elif session and session.login_step and session.login_step.startswith("waiting_payment_url:"):
            title = session.login_step.split(":", 1)[1]
            async with AsyncSessionLocal() as db:
                db.add(PaymentLink(title=title, url=message.text))
                s = (await db.execute(select(AdminSession).where(AdminSession.telegram_id == message.from_user.id))).scalar_one_or_none()
                if s: s.login_step = "none"
                await db.commit()
            await message.answer(f"✅ Ссылка <b>{title}</b> добавлена!", parse_mode="HTML", reply_markup=await payment_links_menu())

        else:
            if await is_admin_authenticated(message.from_user.id):
                await message.answer("Используйте кнопки меню 👇", reply_markup=admin_main_menu_with_webapp())
            else:
                await message.answer("👋 Кто вы?", reply_markup=role_selection_kb())


@router.callback_query(F.data == "admin_payment")
async def admin_payment(callback: CallbackQuery):
    if not await is_admin_authenticated(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True); return
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer("💳 <b>Управление ссылками на оплату</b>", parse_mode="HTML", reply_markup=await payment_links_menu())
    await callback.answer()


@router.callback_query(F.data == "add_payment_link")
async def add_payment_link(callback: CallbackQuery):
    async with AsyncSessionLocal() as db:
        s = (await db.execute(select(AdminSession).where(AdminSession.telegram_id == callback.from_user.id))).scalar_one_or_none()
        if s: s.login_step = "waiting_payment_title"
        await db.commit()
    await callback.message.answer("📝 Введите название ссылки (например: «Сбербанк»):")
    await callback.answer()


@router.callback_query(F.data.startswith("del_payment:"))
async def del_payment_link(callback: CallbackQuery):
    link_id = int(callback.data.split(":")[1])
    async with AsyncSessionLocal() as db:
        await db.execute(delete(PaymentLink).where(PaymentLink.id == link_id))
        await db.commit()
    await callback.message.edit_text("✅ Ссылка удалена!", reply_markup=await payment_links_menu())
    await callback.answer()


@router.callback_query(F.data == "admin_back")
async def admin_back(callback: CallbackQuery):
    await callback.message.edit_text("👨‍🏫 <b>Панель учителя</b>\n\nВыберите действие:", parse_mode="HTML", reply_markup=admin_main_menu_with_webapp())
    await callback.answer()


@router.callback_query(F.data.startswith("approve_booking:"))
async def approve_booking(callback: CallbackQuery):
    booking_id = int(callback.data.split(":")[1])
    async with AsyncSessionLocal() as db:
        booking = (await db.execute(select(Booking).where(Booking.id == booking_id))).scalar_one_or_none()
        if booking:
            booking.status = "approved"
            await db.commit()
            payment_links = (await db.execute(select(PaymentLink).where(PaymentLink.is_active == True))).scalars().all()
            dt_str = booking.slot_datetime.strftime("%d.%m.%Y в %H:%M")
            payment_text = ""
            if payment_links:
                payment_text = "\n\n💳 <b>Ссылки на оплату:</b>\n"
                for link in payment_links:
                    payment_text += f"• <a href='{link.url}'>{link.title}</a>\n"
            try:
                from bot.main import bot
                await bot.send_message(booking.student_telegram_id, f"✅ <b>Урок подтверждён!</b>\n\n📅 <b>{dt_str}</b>\nУчитель подтвердил вашу запись.{payment_text}", parse_mode="HTML")
            except Exception:
                pass
student_info = student_label(booking.student_username, booking.student_name) if booking else "?"
dt_str = booking.slot_datetime.strftime("%d.%m.%Y в %H:%M") if booking else "?"
await callback.message.edit_text(
    f"✅ Бронирование #{booking_id} <b>подтверждено</b>!\n\n👤 Ученик: {student_info}\n📅 {dt_str}",
    parse_mode="HTML"
)
    await callback.answer("Подтверждено!")


@router.callback_query(F.data.startswith("reject_booking:"))
async def reject_booking(callback: CallbackQuery):
    booking_id = int(callback.data.split(":")[1])
    async with AsyncSessionLocal() as db:
        booking = (await db.execute(select(Booking).where(Booking.id == booking_id))).scalar_one_or_none()
        if booking:
            booking.status = "rejected"
            slot = (await db.execute(select(AvailableSlot).where(AvailableSlot.id == booking.slot_id))).scalar_one_or_none()
            if slot: slot.is_booked = False
            await db.commit()
            dt_str = booking.slot_datetime.strftime("%d.%m.%Y в %H:%M")
            try:
                from bot.main import bot
                await bot.send_message(booking.student_telegram_id, f"❌ <b>Запись отклонена</b>\n\nУчитель отклонил запись на {dt_str}.\nВы можете выбрать другое время.", parse_mode="HTML")
            except Exception:
                pass
    await callback.message.edit_text(f"❌ Бронирование #{booking_id} <b>отклонено</b>.", parse_mode="HTML")
    await callback.answer("Отклонено.")


@router.callback_query(F.data == "admin_bookings")
async def admin_bookings(callback: CallbackQuery):
    if not await is_admin_authenticated(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True); return
    async with AsyncSessionLocal() as db:
        bookings = (await db.execute(select(Booking).where(Booking.status == "pending").order_by(Booking.created_at))).scalars().all()
    if not bookings:
        await callback.message.answer("📋 Нет ожидающих подтверждения записей.", reply_markup=admin_main_menu_with_webapp())
    else:
        for b in bookings:
            student_info = f"@{b.student_username}" if b.student_username else b.student_name or "Неизвестно"
            dt_str = b.slot_datetime.strftime("%d.%m.%Y в %H:%M")
            await callback.message.answer(f"📩 <b>Новая запись #{b.id}</b>\n\n👤 Ученик: {student_info}\n📅 Дата: <b>{dt_str}</b>", parse_mode="HTML", reply_markup=booking_approval_kb(b.id))
    await callback.answer()
