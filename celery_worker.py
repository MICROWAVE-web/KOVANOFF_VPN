import logging
import sys
from datetime import datetime, timedelta

from celery import Celery
from decouple import config
from telebot import TeleBot

from headers import ADMINS, DATETIME_FORMAT, tz
from keyboards import get_cancel_subsciption, get_remind_message, get_continue_keyboard, get_cancel_keyboard
from manager import get_user_data, save_user
from panel_3xui import login, delete_client

# Инициализация Celery
app = Celery('tasks', broker='redis://localhost:6379/0')
app.conf.update(
    broker_connection_retry_on_startup=True,
    result_backend='redis://localhost:6379/2',
    task_acks_late=True,  # Подтверждение выполнения задачи только после успешного завершения
    task_reject_on_worker_lost=True,  # Задача будет заново добавлена в очередь, если воркер умер
    worker_max_tasks_per_child=100
)

# Бот
bot = TeleBot(token=config('API_TOKEN'), parse_mode='HTML')

# Логирование
logging.basicConfig(level=logging.INFO, stream=sys.stdout)


def wakeup_admins(message):
    for admin in ADMINS:
        try:
            bot.send_message(chat_id=admin, text=message)
        except Exception as e:
            logging.exception(f"Ошибка при отправке сообщения админу {admin=}")


@app.task
def cancel_subscribtion(user_id, panel_uuid):
    """
    Отмена подписки пользователя.

    :param user_id:
    :param panel_uuid:
    :return:
    """
    try:
        # Проверяем подписку
        user_data = get_user_data(user_id)
        for sub in user_data['subscriptions']:
            if sub['panel_uuid'] == panel_uuid:
                exp_date = datetime.strptime(sub['datetime_expire'], DATETIME_FORMAT).replace(tzinfo=tz)
                now_date = datetime.now(tz) + timedelta(hours=1)
                if exp_date > now_date:
                    logging.info(
                        f"Подписка {user_id=} {panel_uuid=} не будет отменена, тк была продлена до {sub['datetime_expire']}"
                    )
                    return

        # Удаляем клиента
        logging.info(f"User (id: {panel_uuid}) was deleted.")
        api = login()
        delete_client(api, panel_uuid)

        # Деактивируем подписку
        for sub in user_data['subscriptions']:
            if sub['panel_uuid'] == panel_uuid:
                sub['active'] = False
                break
        save_user(user_id, user_data)

    except Exception:
        logging.exception(f"Ошибка при обработке отмены подписки {panel_uuid=} {user_id=}")
        wakeup_admins(f"Ошибка при отмене подписки {panel_uuid=} {user_id=}")
        return

    # Отправка уведомления пользователю
    try:
        bot.send_message(chat_id=user_id, text=get_cancel_subsciption(), reply_markup=get_cancel_keyboard())
    except Exception:
        logging.exception(f"Ошибка при отправке сообщения пользователю {user_id=}, во время окончания подписки")


@app.task
def remind_subscribtion(user_id, days_before_expire, panel_uuid):
    """
    Напоминание пользователю.

    :param user_id:
    :param days_before_expire:
    :param panel_uuid:
    :return:
    """
    try:
        bot.send_message(chat_id=user_id, text=get_remind_message(days_before_expire),
                         reply_markup=get_continue_keyboard(panel_uuid))
    except Exception:
        logging.exception(f"Ошибка при отправке сообщения пользователю {user_id=}, во время напоминанию о подписке")
