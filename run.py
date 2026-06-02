"""
Локальный запуск для разработки (бот + API вместе)
"""
import os
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()


def check_env():
    token = os.getenv("BOT_TOKEN", "")
    admin_id = os.getenv("ADMIN_TELEGRAM_ID", "0")
    if "YOUR_BOT_TOKEN" in token or not token:
        print("❌ Укажите BOT_TOKEN в .env файле!")
        sys.exit(1)
    if "YOUR_TELEGRAM_ID" in admin_id or admin_id == "0":
        print("❌ Укажите ADMIN_TELEGRAM_ID в .env файле!")
        print("   Узнать свой ID: напиши @userinfobot в Telegram")
        sys.exit(1)
    print(f"✅ BOT_TOKEN: ...{token[-8:]}")
    print(f"✅ ADMIN_ID: {admin_id}")
    print(f"✅ API URL: {os.getenv('API_BASE_URL', 'http://localhost:8000')}")


if __name__ == "__main__":
    print("=" * 55)
    print("🎓 Tutor Bot — Локальный запуск")
    print("=" * 55)
    check_env()

    import uvicorn
    port = int(os.getenv("PORT", 8000))
    print(f"\n📅 Календарь учителя: http://localhost:{port}/calendar/admin")
    print(f"📅 Календарь ученика: http://localhost:{port}/calendar/client")
    print(f"\nДля остановки нажмите Ctrl+C")
    print("=" * 55 + "\n")

    uvicorn.run("api.main:app", host="0.0.0.0", port=port, reload=False)
