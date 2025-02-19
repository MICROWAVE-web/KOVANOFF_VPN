import asyncio
import logging
import os
import sys
import traceback
from datetime import datetime, timedelta

# from aiogram.client.default import DefaultBotProperties
# from aiogram.enums import ParseMode
from celery import Celery
from decouple import config
# from aiogram import Bot
from telebot import TeleBot

from headers import ADMINS, DATETIME_FORMAT, tz
from keyboards import get_cancel_subsciption, get_remind_message, get_continue_keyboard, get_cancel_keyboard
from manager import get_user_data, save_user
from panel_3xui import login, delete_client

# Инициализация Celery
app = Celery('tasks', broker='redis://localhost:6379/0')
app.conf.broker_connection_retry_on_startup = True

# Пример настройки бекенда для хранения результатов в Redis
app.conf.result_backend = 'redis://localhost:6379/2'

# Бот
bot = TeleBot(token=config('API_TOKEN'), parse_mode='HTML')

# Логгирвание
logging.basicConfig(level=logging.INFO, stream=sys.stdout)


def wakeup_admins(message):
    async def send_messages():
        for admin in ADMINS:
            try:
                bot.send_message(chat_id=admin, text=message)
            except Exception as e:
                logging.error(f"Failed to send message to admin {admin}")
                traceback.print_exc()

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(send_messages())
    except RuntimeError:
        traceback.print_exc()
        wakeup_admins(f"RuntimeError. Перезапускаю worker")
        os.system("sudo systemctl restart kovanoff_vpn_worker")
    finally:
        loop.close()


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
                    return False
    except Exception as e:
        wakeup_admins("Ошибка при сверке времени подписки")
        traceback.print_exc()
        return True

    try:
        logging.info(f"User (id: {panel_uuid}) was deleted.")
        api = login()
        delete_client(api, panel_uuid)
    except Exception as e:
        if 'Client does not exist' in str(e):
            return True
        else:
            wakeup_admins(f"Ошибка при удалении клиента {panel_uuid=} {user_id=}")
            traceback.print_exc()
            return True

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
        return True

    bot.send_message(chat_id=user_id, text=get_cancel_subsciption(), reply_markup=get_cancel_keyboard())

    return True


@app.task
def remind_subscribtion(user_id, days_before_expire, panel_uuid):
    """

    :param user_id:
    :param days_before_expire:
    :param panel_uuid:
    :return:
    """

    bot.send_message(chat_id=user_id, text=get_remind_message(days_before_expire),
                     reply_markup=get_continue_keyboard(panel_uuid))

    '''async def _snd_prompt(usr_id, days_before_expr, pnl_uuid):
        await bot.send_message(usr_id, text=get_remind_message(days_before_expr),
                               reply_markup=get_continue_keyboard(pnl_uuid))

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(_snd_prompt(user_id, days_before_expire, panel_uuid))
    except RuntimeError:
        traceback.print_exc()
        wakeup_admins(f"RuntimeError. Перезапускаю worker")
        os.system("sudo systemctl restart kovanoff_vpn_worker")
    finally:
        loop.close()'''
