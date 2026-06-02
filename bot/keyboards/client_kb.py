import os
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo


def client_main_menu() -> InlineKeyboardMarkup:
    api_url = os.getenv("API_BASE_URL", "http://localhost:8000")
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="📅 Выбрать дату и время урока",
            web_app=WebAppInfo(url=f"{api_url}/calendar/client")
        )],
        [InlineKeyboardButton(text="📋 Мои записи (±1 неделя)", callback_data="client_my_lessons")],
        [InlineKeyboardButton(text="💳 Способы оплаты", callback_data="client_payment")],
    ])


def admin_main_menu_with_webapp() -> InlineKeyboardMarkup:
    """Меню учителя с WebApp кнопкой для календаря"""
    api_url = os.getenv("API_BASE_URL", "http://localhost:8000")
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="📅 Изменить даты уроков",
            web_app=WebAppInfo(url=f"{api_url}/calendar/admin")
        )],
        [InlineKeyboardButton(text="💳 Редактировать способы оплаты", callback_data="admin_payment")],
        [InlineKeyboardButton(text="📋 Ожидающие подтверждения", callback_data="admin_bookings")],
        [InlineKeyboardButton(text="🚪 Выйти из аккаунта", callback_data="admin_logout")],
    ])
