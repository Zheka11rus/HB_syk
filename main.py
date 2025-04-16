import sqlite3
from datetime import datetime
from telegram import Bot, Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes
from telegram.ext import filters
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import os
import asyncio

# Конфигурация
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")  # Токен из переменных окружения
ADMIN_ID = int(os.getenv("ADMIN_ID", "385919505"))  # ID админа с значением по умолчанию
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

# Проверка, является ли пользователь админом
def is_admin(update: Update):
    return update.effective_user.id == ADMIN_ID

# Добавление дня рождения
def add_birthday(chat_id, name, day, month, year):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('INSERT INTO birthdays (chat_id, name, day, month, year) VALUES (?, ?, ?, ?, ?)', 
                   (chat_id, name, day, month, year))
    conn.commit()
    conn.close()

# Получение списка всех дней рождений
def get_all_birthdays(chat_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('SELECT name, day, month, year FROM birthdays WHERE chat_id = ?', (chat_id,))
    birthdays = cursor.fetchall()
    conn.close()
    return birthdays

# Получение сегодняшних дней рождений с возрастом
def get_today_birthdays():
    today = datetime.now()
    day, month = today.day, today.month
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('SELECT chat_id, name, year FROM birthdays WHERE day = ? AND month = ?', (day, month))
    birthdays = cursor.fetchall()
    conn.close()
    
    result = []
    for chat_id, name, year in birthdays:
        age = today.year - year if year else None
        result.append((chat_id, name, age))
    return result

# Команда /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎂 Бот для уведомлений о днях рождения!\n"
        "Доступные команды:\n"
        "/list — Показать все дни рождения\n"
        "/add Имя День Месяц Год — Добавить день рождения (только админ)\n"
        "Пример: /add Анна 15 7 1990"
    )

# Команда /add (только для админа)
async def add_birthday_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await update.message.reply_text("❌ Только администратор может добавлять дни рождения!")
        return
    
    try:
        _, name, day, month, year = update.message.text.split()
        day, month, year = int(day), int(month), int(year)
        add_birthday(update.message.chat_id, name, day, month, year)
        await update.message.reply_text(f"✅ Добавлено: {name} — {day}.{month}.{year}")
    except Exception as e:
        await update.message.reply_text("❌ Ошибка. Формат: /add Имя День Месяц Год")

# Команда /list
async def list_birthdays(update: Update, context: ContextTypes.DEFAULT_TYPE):
    birthdays = get_all_birthdays(update.message.chat_id)
    if not birthdays:
        await update.message.reply_text("📌 Список дней рождения пуст.")
        return
    
    today = datetime.now()
    response = "📅 Список дней рождения:\n"
    for name, day, month, year in birthdays:
        age = today.year - year if year else "?"
        response += f"• {name} — {day}.{month} ({age} лет)\n"
    
    await update.message.reply_text(response)

# Ежедневная проверка дней рождений
async def check_birthdays(context: ContextTypes.DEFAULT_TYPE):
    birthdays = get_today_birthdays()
    for chat_id, name, age in birthdays:
        message = f"🎉 Сегодня день рождения у {name}!"
        if age:
            message += f" Исполняется {age} лет!"
        await context.bot.send_message(chat_id, message)

async def main():
    init_db()
    
    # Создаем приложение
    application = Application.builder().token(TOKEN).build()
    
    # Добавляем обработчики команд
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("add", add_birthday_command))
    application.add_handler(CommandHandler("list", list_birthdays))

    # Настраиваем планировщик
    scheduler = AsyncIOScheduler()
    scheduler.add_job(check_birthdays, 'cron', hour=9, minute=0, args=[application.job_queue])
    scheduler.start()

    # Запускаем бота
    await application.run_polling()

if __name__ == "__main__":
    asyncio.run(main())
