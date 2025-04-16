import sqlite3
from datetime import datetime
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import os
import asyncio

# Конфигурация
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "385919505"))
DB_NAME = "birthdays.db"

# Инициализация базы данных
def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS birthdays (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER,
            name TEXT,
            day INTEGER,
            month INTEGER,
            year INTEGER
        )
    ''')
    conn.commit()
    conn.close()

def is_admin(update: Update):
    return update.effective_user.id == ADMIN_ID

def add_birthday(chat_id, name, day, month, year):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('INSERT INTO birthdays (chat_id, name, day, month, year) VALUES (?, ?, ?, ?, ?)', 
                   (chat_id, name, day, month, year))
    conn.commit()
    conn.close()

def get_all_birthdays(chat_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('SELECT name, day, month, year FROM birthdays WHERE chat_id = ?', (chat_id,))
    birthdays = cursor.fetchall()
    conn.close()
    return birthdays

def get_today_birthdays():
    today = datetime.now()
    day, month = today.day, today.month
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('SELECT chat_id, name, year FROM birthdays WHERE day = ? AND month = ?', (day, month))
    birthdays = cursor.fetchall()
    conn.close()
    return [(chat_id, name, today.year - year if year else None) for chat_id, name, year in birthdays]

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎂 Бот для уведомлений о днях рождения!\n"
        "Доступные команды:\n"
        "/list — Показать все дни рождения\n"
        "/add Имя День Месяц Год — Добавить день рождения (только админ)\n"
        "Пример: /add Анна 15 7 1990"
    )

async def add_birthday_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await update.message.reply_text("❌ Только администратор может добавлять дни рождения!")
        return
    
    try:
        _, name, day, month, year = update.message.text.split()
        add_birthday(update.message.chat_id, name, int(day), int(month), int(year))
        await update.message.reply_text(f"✅ Добавлено: {name} — {day}.{month}.{year}")
    except Exception:
        await update.message.reply_text("❌ Ошибка. Формат: /add Имя День Месяц Год")

async def list_birthdays(update: Update, context: ContextTypes.DEFAULT_TYPE):
    birthdays = get_all_birthdays(update.message.chat_id)
    if not birthdays:
        await update.message.reply_text("📌 Список дней рождения пуст.")
        return
    
    today = datetime.now()
    response = "📅 Список дней рождения:\n" + "\n".join(
        f"• {name} — {day}.{month} ({today.year - year if year else '?'} лет)"
        for name, day, month, year in birthdays
    )
    await update.message.reply_text(response)

async def check_birthdays(context: ContextTypes.DEFAULT_TYPE):
    for chat_id, name, age in get_today_birthdays():
        message = f"🎉 Сегодня день рождения у {name}!" + (f" Исполняется {age} лет!" if age else "")
        await context.bot.send_message(chat_id, message)

async def main():
    init_db()
    application = Application.builder().token(TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("add", add_birthday_command))
    application.add_handler(CommandHandler("list", list_birthdays))

    scheduler = AsyncIOScheduler()
    scheduler.add_job(check_birthdays, 'cron', hour=9, minute=0, args=[application])
    scheduler.start()

    await application.initialize()
    await application.start()
    await application.updater.start_polling()
    
    try:
        while True:
            await asyncio.sleep(3600)
    except asyncio.CancelledError:
        pass
    finally:
        await application.updater.stop()
        await application.stop()
        await application.shutdown()
        scheduler.shutdown()

if __name__ == "__main__":
    asyncio.run(main())
