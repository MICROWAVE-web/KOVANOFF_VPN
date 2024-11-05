import asyncio

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from celery import Celery

from main import API_TOKEN

# Инициализация Celery
app = Celery('tasks', broker='redis://localhost:6379/0')
app.conf.broker_connection_retry_on_startup = True
bot = Bot(token=API_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))


@app.task
def send_message(user_id, text):
    async def _send_message(): await bot.send_message(user_id, text)

    asyncio.run(_send_message())
