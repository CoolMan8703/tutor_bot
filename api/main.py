import os
import sys
import asyncio
import threading
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from datetime import datetime, timedelta
from typing import Optional

from database import init_db, get_db, AsyncSessionLocal, AvailableSlot, Booking, PaymentLink

app = FastAPI(title="Tutor Bot API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FRONTEND_DIR = os.path.join(os.path.dirname(BASE_DIR), "frontend")
STATIC_DIR = os.path.join(FRONTEND_DIR, "static")

# Создаём папки если не существуют
os.makedirs(STATIC_DIR, exist_ok=True)
os.makedirs(os.path.join(STATIC_DIR, "css"), exist_ok=True)
os.makedirs(os.path.join(STATIC_DIR, "js"), exist_ok=True)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
templates = Jinja2Templates(directory=os.path.join(FRONTEND_DIR, "templates"))

API_SECRET_KEY = os.getenv("API_SECRET_KEY", "supersecretkey")
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")


@app.on_event("startup")
async def startup():
    await init_db()
    bot_token = os.getenv("BOT_TOKEN", "")
    if bot_token and "YOUR_BOT_TOKEN" not in bot_token:
        thread = threading.Thread(target=run_bot_thread, daemon=True)
        thread.start()
        print("🤖 Бот запущен в фоновом потоке")
    # Запускаем фоновые задачи
    asyncio.create_task(background_scheduler())
    print("✅ API сервер запущен")


def run_bot_thread():
    """Запускает бота в отдельном потоке с собственным event loop"""
    import asyncio
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    async def start_bot_no_signals():
        from aiogram import Bot, Dispatcher
        from bot.handlers import admin, client as client_handler

        bot_token = os.getenv("BOT_TOKEN")
        bot = Bot(token=bot_token)

        import bot.main as bot_module
        bot_module.bot = bot

        dp = Dispatcher()
        dp.include_router(admin.router)
        dp.include_router(client_handler.router)
        
        # start_polling без signal handlers — важно для работы в потоке
        await dp.start_polling(bot, handle_signals=False)

    loop.run_until_complete(start_bot_no_signals())

async def background_scheduler():
    """Фоновые задачи: автоудаление слотов + напоминание учителю каждые 4 часа"""
    import bot.main as bot_module
    last_reminder_hour = -1

    while True:
        await asyncio.sleep(60)  # проверка каждую минуту
        now = datetime.utcnow()

        try:
            # ── Задача 1: удалить свободные слоты за 12 часов до начала ──
            cutoff = now + timedelta(hours=12)
            async with AsyncSessionLocal() as db:
                result = await db.execute(
                    select(AvailableSlot).where(
                        AvailableSlot.is_booked == False,
                        AvailableSlot.slot_datetime <= cutoff,
                        AvailableSlot.slot_datetime > now
                    )
                )
                expired_slots = result.scalars().all()
                for slot in expired_slots:
                    await db.delete(slot)
                if expired_slots:
                    await db.commit()
                    print(f"🗑 Удалено {len(expired_slots)} незабронированных слотов (за 12ч)")

            # ── Задача 2: напоминание учителю каждые 4 часа если есть pending ──
            current_4h_block = now.hour // 4
            if current_4h_block != last_reminder_hour:
                last_reminder_hour = current_4h_block
                async with AsyncSessionLocal() as db:
                    result = await db.execute(
                        select(Booking).where(Booking.status == "pending")
                    )
                    pending = result.scalars().all()

                if pending:
                    bot = getattr(bot_module, 'bot', None)
                    if bot:
                        admin_tg_id = int(os.getenv("ADMIN_TELEGRAM_ID", "0"))
                        from bot.keyboards.admin_kb import booking_approval_kb
                        try:
                            await bot.send_message(
                                admin_tg_id,
                                f"🔔 <b>Напоминание!</b>\n\n"
                                f"У вас {len(pending)} заявок, ожидающих подтверждения.\n"
                                f"Нажмите «📋 Ожидающие подтверждения» в меню бота.",
                                parse_mode="HTML"
                            )
                        except Exception as e:
                            print(f"Ошибка напоминания: {e}")

        except Exception as e:
            print(f"Ошибка планировщика: {e}")
# ─── Модели ───────────────────────────────────────────────────────────────────

class AddSlotRequest(BaseModel):
    datetime_str: str
    secret: str

class BookSlotRequest(BaseModel):
    slot_id: int
    student_telegram_id: int
    student_username: Optional[str] = None
    student_name: Optional[str] = None


# ─── Страницы календарей ──────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def root():
    return "<h2>Tutor Bot API работает ✅</h2>"

@app.get("/calendar/admin", response_class=HTMLResponse)
async def admin_calendar(request: Request):
    return templates.TemplateResponse("admin_calendar.html", {
        "request": request,
        "api_url": API_BASE_URL,
        "secret": API_SECRET_KEY
    })

@app.get("/calendar/client", response_class=HTMLResponse)
async def client_calendar(request: Request):
    return templates.TemplateResponse("client_calendar.html", {
        "request": request,
        "api_url": API_BASE_URL
    })


# ─── API: Слоты ───────────────────────────────────────────────────────────────

@app.get("/api/slots")
async def get_slots(db: AsyncSession = Depends(get_db)):
    now = datetime.utcnow()
    result = await db.execute(
        select(AvailableSlot)
        .where(AvailableSlot.slot_datetime >= now)
        .order_by(AvailableSlot.slot_datetime)
    )
    return [{"id": s.id, "datetime": s.slot_datetime.isoformat(), "is_booked": s.is_booked}
            for s in result.scalars().all()]


@app.get("/api/slots/all")
async def get_all_slots(db: AsyncSession = Depends(get_db)):
    """Все слоты (для админа), включая данные ученика по занятым слотам"""
    since = datetime.utcnow() - timedelta(days=30)
    result = await db.execute(
        select(AvailableSlot)
        .where(AvailableSlot.slot_datetime >= since)
        .order_by(AvailableSlot.slot_datetime)
    )
    slots = result.scalars().all()

    booking_result = await db.execute(
        select(Booking).where(Booking.status != "rejected")
    )
    bookings_by_slot = {}
    for b in booking_result.scalars().all():
        bookings_by_slot[b.slot_id] = b

    response = []
    for s in slots:
        item = {"id": s.id, "datetime": s.slot_datetime.isoformat(), "is_booked": s.is_booked}
        booking = bookings_by_slot.get(s.id)
        if s.is_booked and booking:
            item["student"] = f"@{booking.student_username}" if booking.student_username else (booking.student_name or "Неизвестно")
            item["booking_status"] = booking.status
        response.append(item)
    return response


@app.post("/api/slots/add")
async def add_slot(req: AddSlotRequest, db: AsyncSession = Depends(get_db)):
    if req.secret != API_SECRET_KEY:
        raise HTTPException(status_code=403, detail="Неверный ключ доступа")
    try:
        dt = datetime.fromisoformat(req.datetime_str)
    except ValueError:
        raise HTTPException(status_code=400, detail="Неверный формат даты")
    if dt < datetime.utcnow():
        raise HTTPException(status_code=400, detail="Нельзя добавить прошедшее время")
    existing = (await db.execute(select(AvailableSlot).where(AvailableSlot.slot_datetime == dt))).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail="Этот слот уже существует")
    slot = AvailableSlot(slot_datetime=dt)
    db.add(slot)
    await db.commit()
    await db.refresh(slot)
    return {"id": slot.id, "datetime": slot.slot_datetime.isoformat(), "is_booked": False}


@app.delete("/api/slots/{slot_id}")
async def delete_slot(slot_id: int, secret: str, db: AsyncSession = Depends(get_db)):
    if secret != API_SECRET_KEY:
        raise HTTPException(status_code=403, detail="Неверный ключ доступа")
    slot = (await db.execute(select(AvailableSlot).where(AvailableSlot.id == slot_id))).scalar_one_or_none()
    if not slot:
        raise HTTPException(status_code=404, detail="Слот не найден")
    if slot.is_booked:
        raise HTTPException(status_code=400, detail="Нельзя удалить забронированный слот")
    await db.delete(slot)
    await db.commit()
    return {"status": "deleted"}


# ─── API: Бронирования ────────────────────────────────────────────────────────

@app.post("/api/book")
async def book_slot(req: BookSlotRequest, db: AsyncSession = Depends(get_db)):
    slot = (await db.execute(select(AvailableSlot).where(AvailableSlot.id == req.slot_id))).scalar_one_or_none()
    if not slot:
        raise HTTPException(status_code=404, detail="Слот не найден")
    if slot.is_booked:
        raise HTTPException(status_code=409, detail="Слот уже занят")
    if slot.slot_datetime < datetime.utcnow():
        raise HTTPException(status_code=400, detail="Нельзя записаться на прошедшее время")

    slot.is_booked = True
    booking = Booking(
        slot_id=slot.id,
        slot_datetime=slot.slot_datetime,
        student_telegram_id=req.student_telegram_id,
        student_username=req.student_username,
        student_name=req.student_name,
        status="pending"
    )
    db.add(booking)
    await db.commit()
    await db.refresh(booking)

    asyncio.create_task(notify_teacher_new_booking(booking.id))
    return {"booking_id": booking.id, "status": "pending", "message": "Заявка создана. Ожидайте подтверждения."}

@app.delete("/api/bookings/{booking_id}/cancel")
async def cancel_booking(booking_id: int, student_telegram_id: int, db: AsyncSession = Depends(get_db)):
    """Отмена бронирования учеником (только за 12+ часов до начала)"""
    booking = (await db.execute(
        select(Booking).where(
            Booking.id == booking_id,
            Booking.student_telegram_id == student_telegram_id
        )
    )).scalar_one_or_none()

    if not booking:
        raise HTTPException(status_code=404, detail="Бронирование не найдено")
    if booking.status == "rejected":
        raise HTTPException(status_code=400, detail="Бронирование уже отменено")

    # Проверяем 12-часовой лимит
    now = datetime.utcnow()
    if booking.slot_datetime - now < timedelta(hours=12):
        raise HTTPException(status_code=403, detail="Отмена невозможна менее чем за 12 часов до урока")

    # Освобождаем слот
    slot = (await db.execute(
        select(AvailableSlot).where(AvailableSlot.id == booking.slot_id)
    )).scalar_one_or_none()
    if slot:
        slot.is_booked = False

    booking.status = "cancelled"
    await db.commit()

    # Уведомляем учителя
    asyncio.create_task(notify_teacher_cancellation(booking_id))

    return {"status": "cancelled"}


async def notify_teacher_cancellation(booking_id: int):
    """Уведомление учителя об отмене урока учеником"""
    try:
        import bot.main as bot_module
        bot = getattr(bot_module, 'bot', None)
        if not bot:
            return

        async with AsyncSessionLocal() as db:
            booking = (await db.execute(select(Booking).where(Booking.id == booking_id))).scalar_one_or_none()
            if not booking:
                return

        admin_tg_id = int(os.getenv("ADMIN_TELEGRAM_ID", "0"))
        student_info = f"@{booking.student_username}" if booking.student_username else (booking.student_name or "Неизвестно")
        dt_str = booking.slot_datetime.strftime("%d.%m.%Y в %H:%M")
        await bot.send_message(
            admin_tg_id,
            f"❌ <b>Ученик отменил урок!</b>\n\n"
            f"👤 Ученик: {student_info}\n"
            f"📅 Дата: <b>{dt_str}</b>\n\n"
            f"Слот снова свободен.",
            parse_mode="HTML"
        )
    except Exception as e:
        print(f"Ошибка уведомления об отмене: {e}")

@app.get("/api/bookings/my/{telegram_id}")
async def get_my_bookings(telegram_id: int, db: AsyncSession = Depends(get_db)):
    """Будущие бронирования ученика для отображения в календаре"""
    now = datetime.utcnow()
    result = await db.execute(
        select(Booking).where(
            Booking.student_telegram_id == telegram_id,
            Booking.slot_datetime > now,
            Booking.status.in_(["pending", "approved"])
        ).order_by(Booking.slot_datetime)
    )
    bookings = result.scalars().all()
    cancellable_until = now + timedelta(hours=12)
    return [
        {
            "id": b.id,
            "datetime": b.slot_datetime.isoformat(),
            "status": b.status,
            "can_cancel": b.slot_datetime > cancellable_until
        }
        for b in bookings
    ]

async def notify_teacher_new_booking(booking_id: int):
    try:
        admin_tg_id = int(os.getenv("ADMIN_TELEGRAM_ID", "0"))
        import bot.main as bot_module
        bot = getattr(bot_module, 'bot', None)
        if not bot:
            return

        async with AsyncSessionLocal() as db:
            booking = (await db.execute(select(Booking).where(Booking.id == booking_id))).scalar_one_or_none()
            if not booking:
                return

        from bot.keyboards.admin_kb import booking_approval_kb
        student_info = f"@{booking.student_username}" if booking.student_username else booking.student_name or "Неизвестно"
        dt_str = booking.slot_datetime.strftime("%d.%m.%Y в %H:%M")
        await bot.send_message(
            admin_tg_id,
            f"🔔 <b>Новая заявка на урок!</b>\n\n"
            f"👤 Ученик: {student_info}\n"
            f"📅 Дата: <b>{dt_str}</b>\n"
            f"🆔 Заявка: #{booking.id}",
            parse_mode="HTML",
            reply_markup=booking_approval_kb(booking.id)
        )
    except Exception as e:
        print(f"Ошибка уведомления учителя: {e}")


@app.get("/api/bookings/student/{telegram_id}")
async def get_student_bookings(telegram_id: int, db: AsyncSession = Depends(get_db)):
    now = datetime.utcnow()
    result = await db.execute(
        select(Booking).where(
            Booking.student_telegram_id == telegram_id,
            Booking.slot_datetime >= now - timedelta(weeks=1),
            Booking.slot_datetime <= now + timedelta(weeks=1),
            Booking.status != "rejected"
        ).order_by(Booking.slot_datetime)
    )
    return [{"id": b.id, "datetime": b.slot_datetime.isoformat(), "status": b.status}
            for b in result.scalars().all()]


@app.get("/api/payment-links")
async def get_payment_links(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(PaymentLink).where(PaymentLink.is_active == True))
    return [{"id": l.id, "title": l.title, "url": l.url} for l in result.scalars().all()]


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
