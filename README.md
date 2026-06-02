# 🎓 Tutor Bot

Telegram-бот для записи учеников на уроки + веб-календарь.

---

## 🚀 Деплой на Railway (рекомендуется)

### Шаг 1 — Зарегистрируйся на Railway
Перейди на [railway.app](https://railway.app) → войди через GitHub аккаунт.

### Шаг 2 — Создай GitHub репозиторий
1. Зайди на [github.com](https://github.com) → **New repository**
2. Назови например `tutor-bot` → **Create repository**
3. Загрузи все файлы проекта (перетащи папку или через git)

### Шаг 3 — Создай проект в Railway
1. На [railway.app](https://railway.app) нажми **New Project**
2. Выбери **Deploy from GitHub repo**
3. Выбери свой репозиторий `tutor-bot`
4. Railway автоматически начнёт деплой

### Шаг 4 — Добавь переменные окружения
В Railway: **Variables** → добавь каждую переменную:

| Переменная | Значение |
|---|---|
| `BOT_TOKEN` | Токен от @BotFather |
| `ADMIN_TELEGRAM_ID` | Твой числовой ID (от @userinfobot) |
| `ADMIN_LOGIN` | Любой логин, например `teacher` |
| `ADMIN_PASSWORD` | Надёжный пароль |
| `API_SECRET_KEY` | Случайная строка (минимум 32 символа) |
| `API_BASE_URL` | Пока оставь пустым — заполни после шага 5 |

### Шаг 5 — Получи URL приложения
В Railway: **Settings** → **Domains** → **Generate Domain**
Получишь URL вида `https://tutor-bot-xxxx.up.railway.app`

### Шаг 6 — Обнови API_BASE_URL
Вернись в **Variables** и добавь:
```
API_BASE_URL = https://tutor-bot-xxxx.up.railway.app
```
Railway автоматически перезапустит приложение.

### ✅ Готово!
- Бот работает 24/7
- Веб-календарь: `https://твой-url.up.railway.app/calendar/admin`

---

## 💻 Локальный запуск (для разработки)

```bash
pip install -r requirements.txt
# Заполни .env файл
python run.py
```

---

## 📱 Как работает Telegram WebApp

Кнопки «📅 Изменить даты уроков» и «📅 Выбрать дату и время урока» открывают
веб-календарь **прямо внутри Telegram** (не в браузере).

Для этого нужно чтобы API_BASE_URL был HTTPS — Railway даёт это автоматически.
На localhost WebApp не работает (ограничение Telegram), но работает как обычная ссылка.

---

## 🔑 Как пользоваться

**Учитель:**
1. `/start` → введи логин → введи пароль
2. «📅 Изменить даты уроков» → откроется календарь внутри Telegram
3. Добавляй/удаляй слоты
4. При записи ученика — приходит уведомление с кнопками ✅/❌
5. «🚪 Выйти» — выход из режима учителя (переключение на режим ученика)

**Ученик:**
1. `/start` → появляется меню ученика
2. «📅 Выбрать дату и время» → откроется календарь внутри Telegram
3. Выбирает дату → время → заполняет данные → отправляет заявку
4. Ждёт подтверждения в Telegram

---

## 🌐 API Endpoints

| Метод | URL | Описание |
|---|---|---|
| GET | `/api/slots` | Свободные слоты |
| GET | `/api/slots/all` | Все слоты (для админа) |
| POST | `/api/slots/add` | Добавить слот |
| DELETE | `/api/slots/{id}` | Удалить слот |
| POST | `/api/book` | Забронировать |
| GET | `/api/payment-links` | Ссылки на оплату |
| GET | `/calendar/admin` | Календарь учителя |
| GET | `/calendar/client` | Календарь ученика |
