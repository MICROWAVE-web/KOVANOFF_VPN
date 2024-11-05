import asyncio
import traceback

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from celery import Celery
from decouple import config
from yookassa import Configuration, Payment

YOOKASSA_SHOP_ID = config('YOOKASSA_SHOP_ID')
YOOKASSA_SECRET_KEY = config('YOOKASSA_SECRET_KEY')

# Настройка конфигурации ЮKassa
Configuration.account_id = YOOKASSA_SHOP_ID
Configuration.secret_key = YOOKASSA_SECRET_KEY

# Инициализация Celery
app = Celery('tasks', broker='redis://localhost:6379/0')
app.conf.broker_connection_retry_on_startup = True
bot = Bot(token=config('API_TOKEN'), default=DefaultBotProperties(parse_mode=ParseMode.HTML))


async def send_message(user_id, text): await bot.send_message(user_id, text)


@app.task
def send_message(user_id, text):
    asyncio.run(send_message(user_id, text))


@app.task
def cancel_payment(payment_id):
    try:
        print(f"Запрос на отмену транзакции {payment_id}")
        result = Payment.cancel(payment_id)
        print(result)
    except Exception as e:
        traceback.print_exc()
