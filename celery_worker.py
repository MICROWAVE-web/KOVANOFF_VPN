import asyncio
import logging
import sys
import traceback

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from celery import Celery
from decouple import config
from yookassa import Configuration

from keyboards import get_cancel_subsciption, get_remind_message, get_continue_keyboard, get_cancel_keyboard
from manager import get_user_data, save_user
from panel_3xui import login, delete_client

YOOKASSA_SHOP_ID = config('YOOKASSA_SHOP_ID')
YOOKASSA_SECRET_KEY = config('YOOKASSA_SECRET_KEY')

# Настройка конфигурации ЮKassa
Configuration.account_id = YOOKASSA_SHOP_ID
Configuration.secret_key = YOOKASSA_SECRET_KEY

# Инициализация Celery
app = Celery('tasks', broker='redis://localhost:6379/0')
app.conf.broker_connection_retry_on_startup = True
bot = Bot(token=config('API_TOKEN'), default=DefaultBotProperties(parse_mode=ParseMode.HTML))

# Логгирвание
logging.basicConfig(level=logging.INFO, stream=sys.stdout)


async def send_message(user_id, text): await bot.send_message(user_id, text)


@app.task
def send_message(user_id, text):
    asyncio.run(send_message(user_id, text))


@app.task
def cancel_subscribtion(user_id, panel_uuid):
    try:
        logging.info(f"User (id: {panel_uuid}) was deleted.")
        api = login()
        delete_client(api, panel_uuid)
    except Exception as e:
        traceback.print_exc()
    try:
        user_data = get_user_data(user_id)
        for sub in user_data['subscriptions']:
            if sub['panel_uuid'] == panel_uuid:
                sub['active'] = False
                break
        save_user(user_id, user_data)
    except Exception as e:
        traceback.print_exc()

    # TODO: При ошибке уведомить администратора

    async def _snd_prompt(usr_id):
        await bot.send_message(usr_id, text=get_cancel_subsciption(), reply_markup=get_cancel_keyboard())

    asyncio.run(_snd_prompt(user_id))


@app.task
def remind_subscribtion(user_id, days_before_expire, panel_uuid):
    async def _snd_prompt(usr_id, days_before_expr, pnl_uuid):
        await bot.send_message(usr_id, text=get_remind_message(days_before_expr),
                               reply_markup=get_continue_keyboard(pnl_uuid))

    asyncio.run(_snd_prompt(user_id, days_before_expire, panel_uuid))
