import asyncio
import io
import logging
import ssl
import sys
import time
import traceback
import uuid
from datetime import datetime, date, timedelta

import qrcode
import redis
from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, BufferedInputFile, FSInputFile, Message
from aiogram.utils.deep_linking import create_start_link
from aiogram.utils.payload import decode_payload
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web
from telegram.error import RetryAfter
from yookassa import Payment
from yookassa.domain.notification import WebhookNotification

import celery_worker
from headers import ADMINS, router, DATETIME_FORMAT, tz, K_remind, WEBHOOK_PATH, BASE_WEBHOOK_URL, PAYMENT_WEBHOOK_PATH, \
    mode, API_TOKEN, WEBHOOK_SSL_CERT, WEBHOOK_SSL_PRIV, WEBAPP_HOST, WEBAPP_PORT, ACTIVE_COUNT_SUB_LIMIT
from keyboards import *
from manager import *
from panel_3xui import login, add_client, get_client_url, continue_client
from throttle_middleware import ThrottlingMiddleware


async def wakeup_admins(message):
    for admin in ADMINS:
        await bot.send_message(chat_id=admin, text=message)


def get_qr_code(config_url):
    """

    :param config_url:
    :return:
    """
    # Генерируем QR-code
    img = qrcode.make(config_url)
    byte_arr = io.BytesIO()
    img.save(byte_arr, format='PNG')
    byte_arr.seek(0)
    return byte_arr


async def referral_reward(referral):
    if referral == "":
        return
    user_id = referral
    user_data = get_user_data(user_id)
    if user_data is not None:
        if user_data['sale'] >= 30:
            await bot.send_message(user_id, get_sale_limit_message(user_data['sale']))
        else:
            user_data['sale'] += 5
            save_user(user_id, user_data)
            await bot.send_message(user_id, get_sale_increase_message(user_data['sale']))


# Создание реф. ссылок
@router.message(Command('my_ref'))
async def get_ref(message: types.Message):
    user_id = str(message.from_user.id)
    user_data = get_user_data(user_id)
    if user_data is not None:
        link = await create_start_link(bot, user_id, encode=True)
        await bot.send_message(user_id, get_ref_link_message(link))
    else:
        await bot.send_message(user_id, f"Напиши /start")


# Проверка актуалности подписки:
@router.message(Command('cancel_subs'))
async def get_statistic(message: types.Message):
    def cancel_sub(sub):
        exp_date = datetime.strptime(sub['datetime_expire'], DATETIME_FORMAT).replace(tzinfo=tz)
        now_date = datetime.now(tz) + timedelta(hours=1)
        if exp_date < now_date:
            return True
        return False

    user_id = message.from_user.id
    if str(user_id) not in ADMINS:
        await bot.send_message(user_id, get_wrong_command_message())
        return

    suc_cancel = 0
    fail_cancel = 0
    data = load_users()
    for usr_id, user_info in data.items():
        for subscription in user_info.get("subscriptions", []):
            if subscription["active"] is False:
                continue

            output = cancel_sub(subscription)
            if output is True:
                suc_cancel += 1
            elif output is False:
                fail_cancel += 1

    text = f"""
Отменены: {suc_cancel}
Активны: {fail_cancel}"""
    await bot.send_message(user_id, text)


# Статистика
@router.message(Command('statistic'))
async def get_statistic(message: types.Message):
    user_id = message.from_user.id
    if str(user_id) not in ADMINS:
        await bot.send_message(user_id, get_wrong_command_message())
        return
    # Переменные для подсчета
    total_users = 0
    try_period_users_total = 0
    try_period_users_today = 0
    paid_users_total = 0
    paid_users_today = 0
    empty_users = 0

    # Текущая дата для проверки
    today = date.today()

    # Данные о пользователях
    data = load_users()

    # Проходим по каждому пользователю
    for _, user_info in data.items():
        total_users += 1  # Считаем общего пользователя

        # Проверка на try_period
        if user_info.get("try_period", False):
            try_period_users_total += 1

            # Проверяем, если дата операции совпадает с сегодняшней датой
            for subscription in user_info.get("subscriptions", []):
                if subscription["subscription"] == "try_period":
                    operation_date = datetime.strptime(subscription["datetime_operation"], DATETIME_FORMAT).date()
                    if operation_date == today:
                        try_period_users_today += 1
                        break

        # Проверка на подписки
        if len(user_info.get("subscriptions", [])) > 0:
            paid_users_total_fl = False

            # Проверяем, была ли подписка оформлена сегодня
            for subscription in user_info["subscriptions"]:
                operation_date = datetime.strptime(subscription["datetime_operation"], DATETIME_FORMAT).date()
                if subscription["subscription"] != "try_period":
                    paid_users_total_fl = True
                    if operation_date == today:
                        paid_users_today += 1
                        break
            if paid_users_total_fl:
                paid_users_total += 1

        # Проверка на пустого пользователя
        if len(user_info.get("subscriptions", [])) == 0 and user_info.get("try_period", False) is False:
            empty_users += 1

    text = f"""Общая статистика:
1) Общее количество : {total_users}
2) Количество  с пробной подпиской (всего): {try_period_users_total}
3) Количество  с платной подпиской (всего): {paid_users_total}
4) Количество  с пробной подпиской (за сегодня): {try_period_users_today} 
5) Количество  с платной подпиской (за сегодня): {paid_users_today}
6) Количество пустых: {empty_users}"""

    # Вывод статистики
    await bot.send_message(chat_id=user_id, text=text)


# Приветствие
@router.message(CommandStart())
async def send_welcome(message: types.Message, command: CommandObject = None):
    user_id = message.from_user.id

    referral = ""

    # Проверка реферала
    if command and command.args:
        reference = str(decode_payload(command.args))
        if reference != str(user_id):
            referral = reference

    user_data = get_user_data(user_id)
    if user_data is None:
        user_data = {
            'subscriptions': [],
            'referral': referral,
            'try_period': False,
            'sale': 0
        }
        save_user(user_id, user_data)

    await bot.send_message(user_id, text=get_welcome_message(), reply_markup=get_welcome_keyboard())


# Список доступных подписок
@router.callback_query(F.data.startswith('instruction'))
async def get_sub(call: CallbackQuery, state: FSMContext):
    await bot.send_document(chat_id=call.from_user.id,
                            document=FSInputFile('instruction/Инструкция для всех платформ.docx'))
    await state.clear()


# Список доступных подписок
@router.callback_query(F.data == 'get_sub')
async def get_sub(call: CallbackQuery, state: FSMContext):
    user_sale = int(get_user_data(call.from_user.id).get('sale', 0))
    if TEST_PAYMETNS is not True or str(call.from_user.id) in ADMINS:
        await call.message.answer(text=get_subs_message(user_sale)[0], reply_markup=get_subs_keyboard(user_sale)[0])
        await call.message.answer(text=get_subs_message(user_sale)[1], reply_markup=get_subs_keyboard(user_sale)[1])
    else:
        await bot.send_message(call.from_user.id, text=get_service_working_message())
    await state.clear()


# Список доступных подписок
@router.message(Command('buy'))
async def buy_sub(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    user_sale = int(get_user_data(message.from_user.id).get('sale', 0))
    if TEST_PAYMETNS is not True or str(user_id) in ADMINS:
        await bot.send_message(chat_id=user_id, text=get_subs_message(user_sale)[0],
                               reply_markup=get_subs_keyboard(user_sale)[0])
        await bot.send_message(chat_id=user_id, text=get_subs_message(user_sale)[1],
                               reply_markup=get_subs_keyboard(user_sale)[1])
    else:
        await bot.send_message(user_id, text=get_service_working_message())
    await state.clear()


# Вывод подписок пользователя
@router.message(Command('my_subs'))
async def my_subs(message: types.Message):
    """

    :param message:
    :return:
    """
    user_data = get_user_data(message.from_user.id)
    if user_data is None:
        await bot.send_message(chat_id=message.from_user.id, text=get_empty_subscriptions_message())
    elif len(user_data['subscriptions']) > 0:
        active_subs = []
        inactive_subs = []
        subscriptions = user_data['subscriptions']
        for sub in subscriptions:
            status = sub.get('active')
            if status is True:
                active_subs.append(sub)
            else:
                inactive_subs.append(sub)
        await bot.send_message(chat_id=message.from_user.id,
                               text=get_actual_subscriptions_message(active_subs, inactive_subs),
                               reply_markup=get_active_subscriptions_keyboard(active_subs))
    else:
        await bot.send_message(chat_id=message.from_user.id, text=get_empty_subscriptions_message())


# Получение инфо-ии по конкретной подписке пользователя
@router.callback_query(F.data.startswith("get_info_"))
async def get_info(call: CallbackQuery, state: FSMContext):
    """

    :param call:
    :param state:
    :return:
    """
    try:
        panel_uuid = call.data[9:]
        user_id = call.from_user.id
        user_data = get_user_data(user_id)
        if user_data is not None and user_data.get('subscriptions') is not None:
            for sub in user_data['subscriptions']:
                if sub['panel_uuid'] == panel_uuid:
                    api = login()
                    config_url = get_client_url(api, panel_uuid)
                    byte_arr = get_qr_code(config_url)
                    # Высылаем данные пользователю
                    await bot.send_photo(user_id, photo=BufferedInputFile(file=byte_arr.read(), filename="qrcode.png"),
                                         caption=get_success_pay_message(config_url),
                                         reply_markup=get_success_pay_keyboard())
    except Exception:
        await wakeup_admins(f"Ошибка отправки данных пользователю panel_uuid={call.data[9:]} {call.from_user.id=}")
        traceback.print_exc()


# Сохранение данных о подписке
async def save_subscription(user_id, payment, notification, datetime_expire, panel_uuid, try_period=False):
    """
    :param try_period:
    :param user_id:
    :param payment:
    :param notification:
    :param datetime_expire:
    :param panel_uuid:
    :return:
    """
    try:
        user_data = get_user_data(user_id)
        if user_data is None:
            add_user(user_id, {
                'try_period': True if try_period else False,
                'subscriptions': [
                    {
                        'payment_id': notification.object.id if try_period is False else '-',
                        'subscription': payment['subscription'] if try_period is False else 'try_period',
                        'datetime_operation': datetime.now(tz).strftime(DATETIME_FORMAT),
                        'datetime_expire': datetime_expire.strftime(DATETIME_FORMAT),
                        'panel_uuid': panel_uuid,
                        'active': True
                    }
                ],
            })
        else:
            user_data['try_period'] = True if try_period else user_data['try_period']
            user_data['subscriptions'].append(
                {
                    'payment_id': notification.object.id if try_period is False else '-',
                    'subscription': payment['subscription'] if try_period is False else 'try_period',
                    'datetime_operation': datetime.now(tz).strftime(DATETIME_FORMAT),
                    'datetime_expire': datetime_expire.strftime(DATETIME_FORMAT),
                    'panel_uuid': panel_uuid,
                    'active': True
                }
            )
            save_user(user_id, user_data)
    except Exception:
        await wakeup_admins(f"Ошибка сохранения подписки (файл users.json) {user_id=} {panel_uuid=}")
        traceback.print_exc()


# Пробная подписка
@router.callback_query(F.data == "try_period")
async def process_try_period(call: CallbackQuery, state: FSMContext):
    """
    :param call:
    :param state:
    :return:
    """
    try:
        user_id = call.from_user.id
        user_data = get_user_data(user_id)
        if user_data is not None and user_data.get("try_period") is not None and user_data["try_period"] is True:
            await bot.send_message(user_id, get_cancel_try_period_message(), reply_markup=get_cancel_keyboard_aiogram())
        else:

            # Добавляем в 3x-ui
            api = login()
            user_delta = subscriptions['try_period']['period']
            devices_count = subscriptions['try_period']['devices']
            panel_uuid = str(uuid.uuid4())
            logging.info(f"User (id: {panel_uuid}) was created.")
            add_client(api, panel_uuid, devices_count, user_delta)
            config_url = get_client_url(api, panel_uuid)

            datetime_expire = datetime.now(tz) + user_delta

            # Записываем в users.json
            await save_subscription(user_id, None, None, datetime_expire, panel_uuid, try_period=True)

            # Отключаем подписку, через user_delta
            celery_worker.cancel_subscribtion.apply_async((user_id, panel_uuid), eta=datetime_expire)

            byte_arr = get_qr_code(config_url)
            # Высылаем данные пользователю
            await bot.send_photo(user_id, photo=BufferedInputFile(file=byte_arr.read(), filename="qrcode.png"),
                                 caption=get_success_pay_message(config_url),
                                 reply_markup=get_success_pay_keyboard())
        await state.clear()
    except Exception:
        await wakeup_admins(f"Ошибка cоздания триальной подписки {call.from_user.id=}")
        traceback.print_exc()


# Продление подписки
@router.callback_query(F.data.startswith("continue_"))
async def continue_subscribe(call: CallbackQuery, state: FSMContext):
    """

    :param call:
    :param state:
    :return:
    """
    try:
        if TEST_PAYMETNS is True and str(call.from_user.id) not in ADMINS:
            await bot.send_message(call.from_user.id, text=get_service_working_message())
            return

        panel_uuid = call.data[9:45]
        subscription = subscriptions.get(call.data[45:])
        user_id = call.from_user.id
        user_data = get_user_data(user_id)
        if user_data is not None and user_data.get('subscriptions') is not None:
            for sub in user_data['subscriptions']:
                if sub['panel_uuid'] == panel_uuid and sub['active'] is False:
                    await bot.send_message(user_id, text=get_continue_cancell_message(),
                                           reply_markup=get_cancel_keyboard_aiogram())
                    return

        if subscription:
            fin_price = str(int(subscription['price'] * (100 - int(user_data['sale'])) / 100))
            payment = Payment.create({
                "amount": {
                    "value": fin_price,
                    "currency": "RUB"
                },
                "confirmation": {
                    "type": "redirect",
                    "return_url": "https://t.me/kovanoff_vpn_bot"
                },
                "capture": True,
                "description": subscription['name']
            }, uuid.uuid4())

            add_payment(
                payment.id,
                {
                    'user_id': call.from_user.id,
                    'subscription': call.data,
                    'creation': False,
                    'continuation': True,
                    'panel_uuid': panel_uuid
                }
            )

            await call.message.answer(text=get_pay_message(user_data['sale']),
                                      reply_markup=get_pay_keyboard(fin_price, payment.confirmation.confirmation_url))
        else:
            await call.message.answer("Неверная команда. Напишите /start")
        await state.clear()
    except Exception:
        await wakeup_admins(f"Ошибка продления подписки (платёж) {call.from_user.id=}")
        traceback.print_exc()


# Покупка подписки
@router.callback_query(F.data.startswith("month_") | F.data.startswith("year_") | F.data.startswith("testday_"))
async def process_subscribe(call: CallbackQuery, state: FSMContext):
    """

    :param call:
    :param state:
    :return:
    """
    try:
        user_id = call.from_user.id

        if TEST_PAYMETNS is True and str(user_id) not in ADMINS:
            await bot.send_message(user_id, text=get_service_working_message())
            return

        if count_active_subscriptions(user_id) >= ACTIVE_COUNT_SUB_LIMIT:
            await bot.send_message(user_id, text=get_subs_limit_message(ACTIVE_COUNT_SUB_LIMIT))
            return

        subscription = subscriptions.get(call.data)
        if subscription:

            user_data = get_user_data(user_id)

            fin_price = str(int(subscription['price'] * (100 - int(user_data['sale'])) / 100))

            payment = Payment.create({
                "amount": {
                    "value": fin_price,
                    "currency": "RUB"
                },
                "confirmation": {
                    "type": "redirect",
                    "return_url": "https://t.me/kovanoff_vpn_bot"
                },
                "capture": True,
                "description": subscription['name']
            }, uuid.uuid4())

            add_payment(
                payment.id,
                {
                    'user_id': call.from_user.id,
                    'subscription': call.data,
                    'creation': True,
                    'continuation': False,
                    'panel_uuid': ''
                }
            )

            await call.message.answer(text=get_pay_message(user_data['sale']), reply_markup=get_pay_keyboard(fin_price,
                                                                                                             payment.confirmation.confirmation_url))
        else:
            await call.message.answer("Неверная команда. Напишите /start")
        await state.clear()
    except Exception:
        await wakeup_admins(f"Ошибка создания подписки (платёж) {call.from_user.id=}")
        traceback.print_exc()


# Создание нового клиента в 3xui
async def create_new_client(user_id, payment, notification):
    """

    :param user_id:
    :param payment:
    :param notification:
    :return:
    """
    try:
        panel_uuid = str(uuid.uuid4())

        # Добавляем в 3x-ui
        api = login()
        user_delta = subscriptions[payment['subscription']]['period']
        devices_count = subscriptions[payment['subscription']]['devices']
        logging.info(f"User (id: {panel_uuid}) was created.")
        add_client(api, panel_uuid, devices_count, user_delta)

        config_url = get_client_url(api, panel_uuid)

        # Вычисляем времена
        datetime_expire = datetime.now(tz) + user_delta

        datetime_remind = datetime.now(tz) + user_delta * K_remind

        # Записываем в users.json
        await save_subscription(user_id, payment, notification, datetime_expire, panel_uuid)

        remove_payment(notification.object.id)

        # Отключаем подписку, через user_delta
        celery_worker.cancel_subscribtion.apply_async((user_id, panel_uuid), eta=datetime_expire)

        # Создаём напоминание
        celery_worker.remind_subscribtion.apply_async((user_id, (user_delta * (1 - K_remind)).days, panel_uuid),
                                                      eta=datetime_remind)

        byte_arr = get_qr_code(config_url)
        # Высылаем данные пользователю
        await bot.send_photo(user_id, photo=BufferedInputFile(file=byte_arr.read(), filename="qrcode.png"),
                             caption=get_success_pay_message(config_url),
                             reply_markup=get_success_pay_keyboard())
    except Exception as e:
        await wakeup_admins(f"Ошибка при создании клиента {user_id=} {notification.object.id=}")
        traceback.print_exc()


# Продление клиента в 3xui
async def conti_client(user_id, payment, notification):
    """

    :param user_id:
    :param payment:
    :param notification:
    :return:
    """
    try:
        user_data = get_user_data(user_id)
        user_delta = subscriptions[payment['subscription']]['period']
        panel_uuid = payment['panel_uuid']
        for sub in user_data['subscriptions']:
            if sub['panel_uuid'] == panel_uuid:
                new_datetime_expire = datetime.strptime(sub['datetime_expire'], DATETIME_FORMAT).date() + user_delta
                datetime_remind = datetime.strptime(sub['datetime_expire'],
                                                    DATETIME_FORMAT).date() + user_delta * K_remind

                # Продлеваем в 3x-ui
                api = login()
                continue_client(api, panel_uuid, new_datetime_expire)
                sub['payment_id'] = notification.object.id
                sub['datetime_expire'] = new_datetime_expire.strftime(DATETIME_FORMAT)

                save_user(user_id, user_data)

                remove_payment(notification.object.id)

                # Отключаем подписку, через user_delta
                celery_worker.cancel_subscribtion.apply_async((user_id, panel_uuid), eta=new_datetime_expire)

                # Создаём напоминание
                celery_worker.remind_subscribtion.apply_async((user_id, (user_delta * (1 - K_remind)).days, panel_uuid),
                                                              eta=datetime_remind)

                # Уведомляем об успешном продлении подписки
                await bot.send_message(user_id,
                                       text=get_success_continue_message(new_datetime_expire.strftime(DATETIME_FORMAT)))
                return
    except Exception as e:
        await wakeup_admins(f"Ошибка продления подписки {user_id=} {notification.object.id=}")
        traceback.print_exc()


# Обработчик webhook для платежной системы
async def payment_webhook_handler(request):
    try:
        data = await request.json()
        notification = WebhookNotification(data)
        if notification.event == 'payment.succeeded':
            logging.info(f"Payment succeeded for payment id: {notification.object.id}")

            payment = get_payment(notification.object.id)
            if payment is None:
                return web.Response(status=200)

            user_id = payment['user_id']
            payments = get_user_payments(user_id)

            if payments is not None and notification.object.id in payments:
                return web.Response(status=200)

            if payment['creation'] is True:
                # Создаём нового клиента
                await create_new_client(user_id, payment, notification)

                # Вознаграждаем реферала
                user_data = get_user_data(user_id)
                await referral_reward(user_data['referral'])
                user_data['referral'] = ""
                save_user(user_id, user_data)

            elif payment['continuation'] is True:
                # Продлеваем клиента
                await conti_client(user_id, payment, notification)

            return web.Response(status=200)

        elif notification.event == 'payment.canceled':
            logging.info(f"Payment canceled for payment id: {notification.object.id}")

            payment = get_payment(notification.object.id)
            if payment is None:
                return web.Response(status=200)

            user_id = payment['user_id']
            payments = get_user_payments(user_id)

            if payments is not None and notification.object.id in payments:
                return web.Response(status=200)

            sub = payment['subscription']
            sub_name = subscriptions[sub]['name']
            try:
                await bot.send_message(user_id, get_canceled_pay_message(),
                                       reply_markup=get_canceled_pay_keyboard(sub_name, sub))
            except Exception as e:
                if 'bot was blocked by the user' in str(e):
                    pass
                else:
                    raise

            remove_payment(notification.object.id)

            return web.Response(status=200)

        else:
            print('Unrecognized event type')
    except Exception as e:
        traceback.print_exc()
        await wakeup_admins(f"Ошибка обработки webhook: {str(e)}")
        logging.error(f"Error processing payment webhook: {str(e)}")
        return web.Response(status=500)


# Обработчик команды /alert
@router.message(Command("alert"))
async def alert_handler(message: Message):
    # Проверяем, является ли пользователь администратором
    user_id = message.from_user.id
    if str(user_id) not in ADMINS:
        await bot.send_message(user_id, get_wrong_command_message())
        return

    # Получаем текст сообщения из команды
    alert_text = message.text.split(" ", 1)
    if len(alert_text) < 2:
        await message.reply("❗ Используйте команду в формате: /alert <текст>")
        return

    message_text = alert_text[1]

    # Подтверждение начала рассылки
    await message.reply("✅ Начинаю рассылку...")

    # Запускаем массовую рассылку
    success_count, failed_count = await broadcast_message(message_text)

    # Отправляем отчет об успешности рассылки
    await message.reply(f"📢 Рассылка завершена!\n✅ Успешно: {success_count}\n❌ Ошибки: {failed_count}")


# Функция для отправки массового сообщения
async def broadcast_message(message_text: str):
    users = get_users_id()
    success_count = 0
    failed_count = 0

    for user_id in users:
        try:
            await bot.send_message(chat_id=user_id, text=message_text)
            success_count += 1
        except RetryAfter as e:
            print(f"Превышен лимит запросов. Ожидаем {e.retry_after} секунд...")
            await asyncio.sleep(e.retry_after)
            continue
        except Exception as e:
            print(f"Ошибка при отправке пользователю {user_id}: {e}")
            failed_count += 1

        # Делаем небольшую паузу, чтобы избежать ограничений API Telegram
        await asyncio.sleep(0.05)

    return success_count, failed_count


# Обработчик пользовательского соглашения
async def user_agreement(request):
    with open('user_agreement/agreement.html', 'r', encoding='utf-8') as f:
        return web.Response(text=f.read(), content_type='text/html')


# Обработчик пользовательского соглашения
async def landing_page(request):
    with open('landing/index.html', 'r', encoding='utf-8') as f:
        return web.Response(text=f.read(), content_type='text/html')


# Обработчик пользовательского соглашения
async def yandex_verification(request):
    with open('yandex_verification/yandex_f70dd47ee8e11ab5.html', 'r', encoding='utf-8') as f:
        return web.Response(text=f.read(), content_type='text/html')


async def on_startup(bot: Bot) -> None:
    webhook_url = f"{BASE_WEBHOOK_URL}{WEBHOOK_PATH}"
    webhook_info = await bot.get_webhook_info()
    if webhook_info.url != webhook_url:
        await bot.set_webhook(
            url=webhook_url,
        )


async def local_startup(bot: Bot) -> None:
    await bot.delete_webhook()
    time.sleep(3)
    await dp.start_polling(bot)


if __name__ == '__main__':
    # Настройка логирования
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)

    dp = Dispatcher()

    bot = Bot(token=API_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))

    if mode == "local":
        dp.include_router(router)
        # Локальный запуск бота
        asyncio.run(local_startup(bot))
    else:
        router.message.middleware(ThrottlingMiddleware(redis.Redis(host='localhost', port=6379, db=1)))
        dp.include_router(router)

        dp.startup.register(on_startup)

        app = web.Application()
        app.router.add_post(PAYMENT_WEBHOOK_PATH, payment_webhook_handler)
        app.router.add_get('/user_agreement', user_agreement)

        # Страница лендинг
        app.router.add_static('/assets/',
                              path='landing/assets',
                              name='assets')
        app.router.add_get('/', landing_page)

        # Яндекс проверка
        # app.router.add_get('/', yandex_verification)

        webhook_requests_handler = SimpleRequestHandler(
            dispatcher=dp,
            bot=bot,
        )
        # Register webhook handler on application
        webhook_requests_handler.register(app, path=WEBHOOK_PATH)

        # Mount dispatcher startup and shutdown hooks to aiohttp application
        setup_application(app, dp, bot=bot)

        # Generate SSL context
        context = ssl.SSLContext(ssl.PROTOCOL_TLSv1_2)
        context.load_cert_chain(WEBHOOK_SSL_CERT, WEBHOOK_SSL_PRIV)

        # And finally start webserver
        web.run_app(app, host=WEBAPP_HOST, port=WEBAPP_PORT, ssl_context=context)
