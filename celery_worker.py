import asyncio
import logging
import sys
import traceback
from datetime import datetime, timedelta

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from celery import Celery
from decouple import config

from headers import ADMINS, DATETIME_FORMAT, tz
from keyboards import get_cancel_subsciption, get_remind_message, get_continue_keyboard, get_cancel_keyboard
from manager import get_user_data, save_user
from panel_3xui import login, delete_client

# Инициализация Celery
app = Celery('tasks', broker='redis://localhost:6379/0')
app.conf.broker_connection_retry_on_startup = True

# Бот
bot = Bot(token=config('API_TOKEN'), default=DefaultBotProperties(parse_mode=ParseMode.HTML))

# Логгирвание
logging.basicConfig(level=logging.INFO, stream=sys.stdout)


async def _send_message(user_id, text): await bot.send_message(user_id, text)


def wakeup_admins(message):
    for admin in ADMINS:
        asyncio.run(_send_message(admin, message))


@app.task
def send_message(user_id, text):
    """

    :param user_id:
    :param text:
    :return:
    """
    asyncio.run(_send_message(user_id, text))


@app.task
def cancel_subscribtion(user_id, panel_uuid):
    """

    :param user_id:
    :param panel_uuid:
    :return:
    """
    try:
        user_data = get_user_data(user_id)
        for sub in user_data['subscriptions']:
            if sub['panel_uuid'] == panel_uuid:
                exp_date = datetime.strptime(sub['datetime_expire'], DATETIME_FORMAT).replace(tzinfo=tz)
                now_date = datetime.now(tz) + timedelta(hours=1)
                if exp_date > now_date:
                    logging.info(
                        f"Подписка {user_id=} {panel_uuid=} не будет отменена, тк была продлена до {sub['datetime_expire']}")
                    return
    except Exception as e:
        wakeup_admins("Ошибка при сверке времени подписки")
        traceback.print_exc()
    try:
        logging.info(f"User (id: {panel_uuid}) was deleted.")
        api = login()
        delete_client(api, panel_uuid)
    except Exception as e:
        wakeup_admins(f"Ошибка при удалении клиента {panel_uuid=} {user_id=}")
        traceback.print_exc()
    try:
        user_data = get_user_data(user_id)
        for sub in user_data['subscriptions']:
            if sub['panel_uuid'] == panel_uuid:
                sub['active'] = False
                break
        save_user(user_id, user_data)
    except Exception as e:
        wakeup_admins(f"Ошибка при деактивации подписки клиента {panel_uuid=} {user_id=}")
        traceback.print_exc()

    async def _snd_prompt(usr_id):
        await bot.send_message(usr_id, text=get_cancel_subsciption(), reply_markup=get_cancel_keyboard())

    asyncio.run(_snd_prompt(user_id))


@app.task
def remind_subscribtion(user_id, days_before_expire, panel_uuid):
    """

    :param user_id:
    :param days_before_expire:
    :param panel_uuid:
    :return:
    """

    async def _snd_prompt(usr_id, days_before_expr, pnl_uuid):
        await bot.send_message(usr_id, text=get_remind_message(days_before_expr),
                               reply_markup=get_continue_keyboard(pnl_uuid))

    asyncio.run(_snd_prompt(user_id, days_before_expire, panel_uuid))
