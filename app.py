import sqlite3
from datetime import datetime
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from flask import Flask, request, render_template
import asyncio
from dotenv import load_dotenv
import os
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Загрузка переменных окружения из .env
load_dotenv()

# Инициализация Telegram-бота
API_TOKEN = os.getenv("TELEGRAM_TOKEN")
if not API_TOKEN:
    raise ValueError("TELEGRAM_TOKEN не найден в .env файле")
bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# Инициализация Flask
flask_app = Flask(__name__)

# Инициализация планировщика
scheduler = AsyncIOScheduler()

# Инициализация базы данных


def init_db():
    try:
        conn = sqlite3.connect("reminders.db")
        c = conn.cursor()
        c.execute(
            """CREATE TABLE IF NOT EXISTS reminders
                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                      user_id INTEGER,
                      description TEXT,
                      reminder_time TEXT,
                      status TEXT)"""
        )
        conn.commit()
        logger.info(
            "База данных и таблица reminders успешно созданы " "или уже существуют"
        )
    except Exception as e:
        logger.error(f"Ошибка при создании базы данных: {str(e)}")
    finally:
        conn.close()


# Telegram: Обработчик команды /start


@dp.message(Command("start"))
async def send_welcome(message: types.Message):
    await message.reply(
        f"Привет! Я бот-напоминалка. Твой ID: {message.from_user.id}\n"
        "Команды:\n/add Описание YYYY-MM-DD HH:MM\n/list\n/delete ID"
    )


# Telegram: Добавление напоминания


@dp.message(Command("add"))
async def add_reminder(message: types.Message):
    try:
        logger.info(f"Получена команда: '{message.text}'")
        parts = message.text.strip().split(maxsplit=1)
        if len(parts) < 2:
            raise ValueError("Недостаточно аргументов")
        args = parts[1].rsplit(" ", 2)
        if len(args) != 3:
            raise ValueError(f"Неверное количество аргументов: {args}")
        description, date, time = args
        logger.info(f"Описание: '{description}', Дата: '{date}', Время: '{time}'")
        reminder_time = datetime.strptime(f"{date} {time}", "%Y-%m-%d %H:%M")
        conn = sqlite3.connect("reminders.db")
        c = conn.cursor()
        c.execute(
            "INSERT INTO reminders (user_id, description, reminder_time, status) "
            "VALUES (?, ?, ?, ?)",
            (
                message.from_user.id,
                description,
                reminder_time.strftime("%Y-%m-%d %H:%M"),
                "pending",
            ),
        )
        conn.commit()
        await message.reply(f"Напоминание '{description}' добавлено на {date} {time}")
    except Exception as e:
        logger.error(f"Ошибка при добавлении напоминания: {str(e)}")
        await message.reply("Ошибка! Формат: /add Описание YYYY-MM-DD HH:MM")
    finally:
        conn.close()


# Telegram: Список напоминаний


@dp.message(Command("list"))
async def list_reminders(message: types.Message):
    try:
        conn = sqlite3.connect("reminders.db")
        c = conn.cursor()
        c.execute(
            "SELECT id, description, reminder_time FROM reminders "
            "WHERE user_id = ? AND status = 'pending'",
            (message.from_user.id,),
        )
        reminders = c.fetchall()
        if reminders:
            response = "Ваши напоминания:\n" + "\n".join(
                [f"ID: {r[0]} | {r[1]} | {r[2]}" for r in reminders]
            )
        else:
            response = "У вас нет напоминаний."
        await message.reply(response)
    except Exception as e:
        logger.error(f"Ошибка при получении списка напоминаний: {str(e)}")
        await message.reply("Ошибка при получении списка напоминаний")
    finally:
        conn.close()


# Telegram: Удаление напоминания


@dp.message(Command("delete"))
async def delete_reminder(message: types.Message):
    try:
        reminder_id = int(message.text.split()[1])
        conn = sqlite3.connect("reminders.db")
        c = conn.cursor()
        c.execute(
            "DELETE FROM reminders WHERE id = ? AND user_id = ?",
            (reminder_id, message.from_user.id),
        )
        conn.commit()
        await message.reply(f"Напоминание ID {reminder_id} удалено.")
    except Exception as e:
        logger.error(f"Ошибка при удалении: {str(e)}")
        await message.reply("Ошибка! Формат: /delete ID")
    finally:
        conn.close()


# Планировщик: Отправка напоминаний


async def check_reminders():
    try:
        conn = sqlite3.connect("reminders.db")
        c = conn.cursor()
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M")
        c.execute(
            "SELECT id, user_id, description, reminder_time FROM reminders "
            "WHERE reminder_time = ? AND status = 'pending'",
            (current_time,),
        )
        reminders = c.fetchall()
        for reminder in reminders:
            await bot.send_message(reminder[1], f"Напоминание: {reminder[2]}")
            c.execute(
                "UPDATE reminders SET status = 'sent' WHERE id = ?", (reminder[0],)
            )
        conn.commit()
    except Exception as e:
        logger.error(f"Ошибка в планировщике: {str(e)}")
    finally:
        conn.close()


# Flask: Главная страница с формой


@flask_app.route("/", methods=["GET", "POST"])
def index():
    try:
        if request.method == "POST":
            user_id = request.form["user_id"]
            description = request.form["description"]
            date = request.form["date"]
            time = request.form["time"]
            reminder_time = datetime.strptime(f"{date} {time}", "%Y-%m-%d %H:%M")
            conn = sqlite3.connect("reminders.db")
            c = conn.cursor()
            c.execute(
                "INSERT INTO reminders (user_id, description, reminder_time, status) "
                "VALUES (?, ?, ?, ?)",
                (
                    user_id,
                    description,
                    reminder_time.strftime("%Y-%m-%d %H:%M"),
                    "pending",
                ),
            )
            conn.commit()
            return "Напоминание добавлено!"
        return render_template("index.html")
    except Exception as e:
        logger.error(f"Ошибка в веб-форме: {e}")
        return f"Ошибка: {e}"
    finally:
        if "conn" in locals():
            conn.close()


# Flask: Список напоминаний


@flask_app.route("/list/<user_id>")
def list_web(user_id):
    try:
        conn = sqlite3.connect("reminders.db")
        c = conn.cursor()
        c.execute(
            "SELECT id, description, reminder_time FROM reminders "
            "WHERE user_id = ? AND status = 'pending'",
            (user_id,),
        )
        reminders = c.fetchall()
        return render_template("list.html", reminders=reminders, user_id=user_id)
    except Exception as e:
        logger.error(f"Ошибка при получении списка веб: {str(e)}")
        return f"Ошибка: {str(e)}"
    finally:
        conn.close()


# Запуск


async def on_startup():
    scheduler.add_job(check_reminders, "interval", seconds=60)
    scheduler.start()
    logger.info("Планировщик запущен")


async def main():
    init_db()  # Создаем базу данных при запуске
    await on_startup()
    # Запускаем Flask в отдельном потоке
    from threading import Thread

    Thread(target=lambda: flask_app.run(host="0.0.0.0", port=5000)).start()
    # Запускаем Telegram-бот
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
