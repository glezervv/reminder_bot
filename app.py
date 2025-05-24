import sqlite3
from datetime import datetime
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from flask import Flask, request, render_template
import asyncio

# Инициализация Telegram-бота
API_TOKEN = 'YOUR_BOT_TOKEN'  # Замените на ваш токен
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

# Инициализация Flask
flask_app = Flask(__name__)

# Инициализация планировщика
scheduler = AsyncIOScheduler()

# Инициализация базы данных
def init_db():
    conn = SQLITE3.connect('reminders.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS reminders
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_id INTEGER,
                  description TEXT,
                  reminder_time TEXT,
                  status TEXT)''')
    conn.commit()
    conn.close()

# Telegram: Обработчик команды /start
@dp.message_handler(commands=['start'])
async def send_welcome(message: types.Message):
    await message.reply("Привет! Я бот-напоминалка.\n"
                       "Команды:\n/add Описание YYYY-MM-DD HH:MM\n/list\n/delete ID")

# Telegram: Добавление напоминания
@dp.message_handler(commands=['add'])
async def add_reminder(message: types.Message):
    try:
        args = message.text.split(maxsplit=1)[1].rsplit(' ', 2)
        description, date, time = args
        reminder_time = datetime.strptime(f"{date} {time}", "%Y-%m-%d %H:%M")
        conn = sqlite3.connect('reminders.db')
        c = conn.cursor()
        c.execute("INSERT INTO reminders (user_id, description, reminder_time, status) VALUES (?, ?, ?, ?)",
                  (message.from_user.id, description, reminder_time.strftime("%Y-%m-%d %H:%M"), "pending"))
        conn.commit()
        conn.close()
        await message.reply(f"Напоминание '{description}' добавлено на {date} {time}")
    except Exception as e:
        await message.reply("Ошибка! Формат: /add Описание YYYY-MM-DD HH:MM")

# Telegram: Список напоминаний
@dp.message_handler(commands=['list'])
async def list_reminders(message: types.Message):
    conn = sqlite3.connect('reminders.db')
    c = conn.cursor()
    c.execute("SELECT id, description, reminder_time FROM reminders WHERE user_id = ? AND status = 'pending'",
              (message.from_user.id,))
    reminders = c.fetchall()
    conn.close()
    if reminders:
        response = "Ваши напоминания:\n" + "\n".join([f"ID: {r[0]} | {r[1]} | {r[2]}" for r in reminders])
    else:
        response = "У вас нет напоминаний."
    await message.reply(response)

# Telegram: Удаление напоминания
@dp.message_handler(commands=['delete'])
async def delete_reminder(message: types.Message):
    try:
        reminder_id = int(message.text.split()[1])
        conn = sqlite3.connect('reminders.db')
        c = conn.cursor()
        c.execute("DELETE FROM reminders WHERE id = ? AND user_id = ?", (reminder_id, message.from_user.id))
        conn.commit()
        conn.close()
        await message.reply(f"Напоминание ID {reminder_id} удалено.")
    except Exception as e:
        await message.reply("Ошибка! Формат: /delete ID")

# Планировщик: Отправка напоминаний
async def check_reminders():
    conn = sqlite3.connect('reminders.db')
    c = conn.cursor()
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M")
    c.execute("SELECT id, user_id, description, reminder_time FROM reminders WHERE reminder_time = ? AND status = 'pending'",
              (current_time,))
    reminders = c.fetchall()
    for reminder in reminders:
        await bot.send_message(reminder[1], f"Напоминание: {reminder[2]}")
        c.execute("UPDATE reminders SET status = 'sent' WHERE id = ?", (reminder[0],))
    conn.commit()
    conn.close()

# Flask: Главная страница с формой
@flask_app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        user_id = request.form['user_id']
        description = request.form['description']
        date = request.form['date']
        time = request.form['time']
        try:
            reminder_time = datetime.strptime(f"{date} {time}", "%Y-%m-%d %H:%M")
            conn = sqlite3.connect('reminders.db')
            c = conn.cursor()
            c.execute("INSERT INTO reminders (user_id, description, reminder_time, status) VALUES (?, ?, ?, ?)",
                      (user_id, description, reminder_time.strftime("%Y-%m-%d %H:%M"), "pending"))
            conn.commit()
            conn.close()
            return "Напоминание добавлено!"
        except Exception as e:
            return f"Ошибка: {str(e)}"
    return render_template('index.html')

# Flask: Список напоминаний
@flask_app.route('/list/<user_id>')
def list_web(user_id):
    conn = sqlite3.connect('reminders.db')
    c = conn.cursor()
    c.execute("SELECT id, description, reminder_time FROM reminders WHERE user_id = ? AND status = 'pending'",
              (user_id,))
    reminders = c.fetchall()
    conn.close()
    return render_template('list.html', reminders=reminders, user_id=user_id)

# Запуск
async def on_startup(_):
    init_db()
    scheduler.add_job(check_reminders, 'interval', seconds=60)
    scheduler.start()

if __name__ == '__main__':
    from threading import Thread
    Thread(target=lambda: flask_app.run(port=5000)).start()
    executor.start_polling(dp, skip_updates=True, on_startup=on_startup)