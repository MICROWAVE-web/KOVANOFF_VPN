import asyncio
import io
import logging
import ssl
import sys
import time
import traceback
import uuid
from datetime import datetime, timedelta

import pytz
import qrcode
import redis
from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, BufferedInputFile
from aiogram.utils.payload import decode_payload
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web
from decouple import config
from yookassa import Payment, Configuration
from yookassa.domain.notification import WebhookNotification

import celery_worker
from keyboards import *
from manager import *
from panel_3xui import login, add_client, get_client_url, continue_client
from throttle_middleware import ThrottlingMiddleware

# Токер телеграмм
API_TOKEN = config('API_TOKEN')

# Id администраторов
ADMINS = config('ADMINS').split(',')

# Юкасса
YOOKASSA_SHOP_ID = config('YOOKASSA_SHOP_ID')
YOOKASSA_SECRET_KEY = config('YOOKASSA_SECRET_KEY')

# Настройка webhook
BASE_WEBHOOK_URL = f'https://{config("WEBHOOK_DOMAIN")}:443'
WEBHOOK_PATH = '/webhook'
PAYMENT_WEBHOOK_PATH = '/payment-webhook'

WEBAPP_HOST = '127.0.0.1'
WEBAPP_PORT = int(config("WEBAPP_PORT"))

WEBHOOK_SECRET = config('WEBHOOK_SECRET')

WEBHOOK_SSL_CERT = config('WEBHOOK_SSL_CERT')
WEBHOOK_SSL_PRIV = config('WEBHOOK_SSL_PRIV')

# Формат времени
DATETIME_FORMAT = "%Y-%m-%d %H:%M"

# defining the timezone
tz = pytz.timezone('Europe/Moscow')

# Роутер
router = Router()

# Режим проограммы
mode = config('MODE')

# Настройка конфигурации ЮKassa
Configuration.account_id = YOOKASSA_SHOP_ID
Configuration.secret_key = YOOKASSA_SECRET_KEY


def wakeup_admins(message):
    for admin in ADMINS:
        bot.send_message(chat_id=admin, text=message)


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


def referral_reward(referral):
    user_id = referral
    user_data = get_user_data(user_id)
    if user_data['sale'] >= 15:
        bot.send_message(user_id, get_sale_limit_message(user_data['sale']))
    else:
        user_data['sale'] += 3
        save_user(user_id, user_data)
        bot.send_message(user_id, get_sale_increase_message(user_data['sale']))


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

    await message.reply(text=get_welcome_message(), reply_markup=get_welcome_keyboard())


# Список доступных подписок
@router.callback_query(F.data == 'get_sub')
async def get_sub(call: CallbackQuery, state: FSMContext):
    await call.message.answer(text=get_subs_message()[0], reply_markup=get_subs_keyboard()[0])
    await call.message.answer(text=get_subs_message()[1], reply_markup=get_subs_keyboard()[1])
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
        await message.answer(text=get_empty_subscriptions_message())
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
        await message.answer(text=get_actual_subscriptions_message(active_subs, inactive_subs),
                             reply_markup=get_active_subscriptions_keyboard(active_subs))


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
        wakeup_admins(f"Ошибка отправки данных пользователю panel_uuid={call.data[9:]} {call.from_user.id=}")
        traceback.print_exc()


# Сохранение данных о подписке
def save_subscription(user_id, payment, notification, datetime_expire, panel_uuid, try_period=False):
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
            user_data['try_period'] = True if try_period else False
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
        wakeup_admins(f"Ошибка сохранения подписки (файл users.json) {user_id=} {panel_uuid=}")
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
            await bot.send_message(user_id, get_cancel_try_period_message(), reply_markup=get_cancel_keyboard())
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
            save_subscription(user_id, None, None, datetime_expire, panel_uuid, try_period=True)

            # Отключаем подписку, через user_delta
            celery_worker.cancel_subscribtion.apply_async((user_id, panel_uuid), eta=datetime_expire)

            byte_arr = get_qr_code(config_url)
            # Высылаем данные пользователю
            await bot.send_photo(user_id, photo=BufferedInputFile(file=byte_arr.read(), filename="qrcode.png"),
                                 caption=get_success_pay_message(config_url),
                                 reply_markup=get_success_pay_keyboard())
        await state.clear()
    except Exception:
        wakeup_admins(f"Ошибка cоздания триальной подписки {call.from_user.id=}")
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
        panel_uuid = call.data[9:45]
        subscription = subscriptions.get(call.data[45:])
        user_id = call.from_user.id
        user_data = get_user_data(user_id)
        if user_data is not None and user_data.get('subscriptions') is not None:
            for sub in user_data['subscriptions']:
                if sub['panel_uuid'] == panel_uuid and sub['active'] is False:
                    await bot.send_message(user_id, text=get_continue_cancell_message(),
                                           reply_markup=get_cancel_keyboard())
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
        wakeup_admins(f"Ошибка продления подписки (платёж) {call.from_user.id=}")
        traceback.print_exc()


# Покупка подписки
@router.callback_query(F.data.startswith("month_") | F.data.startswith("year_"))
async def process_subscribe(call: CallbackQuery, state: FSMContext):
    """

    :param call:
    :param state:
    :return:
    """
    try:
        subscription = subscriptions.get(call.data)
        if subscription:
            user_id = call.from_user.id
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

            referral_reward(user_data['referral'])
            user_data['referral'] = ""
            save_user(user_id, user_data)

            await call.message.answer(text=get_pay_message(user_data['sale']), reply_markup=get_pay_keyboard(fin_price,
                                                                                                             payment.confirmation.confirmation_url))
        else:
            await call.message.answer("Неверная команда. Напишите /start")
        await state.clear()
    except Exception:
        wakeup_admins(f"Ошибка создания подписки (платёж) {call.from_user.id=}")
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
        days_before_expire = 4
        datetime_remind = datetime_expire - timedelta(days=days_before_expire)

        # Записываем в users.json
        save_subscription(user_id, payment, notification, datetime_expire, panel_uuid)

        remove_payment(notification.object.id)

        # Отключаем подписку, через user_delta
        celery_worker.cancel_subscribtion.apply_async((user_id, panel_uuid), eta=datetime_expire)

        # Создаём напоминание
        celery_worker.remind_subscribtion.apply_async((user_id, days_before_expire, panel_uuid), eta=datetime_remind)

        byte_arr = get_qr_code(config_url)
        # Высылаем данные пользователю
        await bot.send_photo(user_id, photo=BufferedInputFile(file=byte_arr.read(), filename="qrcode.png"),
                             caption=get_success_pay_message(config_url),
                             reply_markup=get_success_pay_keyboard())
    except Exception as e:
        wakeup_admins(f"Ошибка при создании клиента {user_id=} {notification.object.id=}")
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
        panel_uuid = payment['panel_uuid']
        for sub in user_data['subscriptions']:
            if sub['panel_uuid'] == panel_uuid:
                user_sub = sub['subscription']
                new_datetime_expire = datetime.strptime(sub['datetime_expire'], DATETIME_FORMAT).date() + \
                                      subscriptions[user_sub]['period']

                api = login()
                continue_client(api, panel_uuid, new_datetime_expire)
                sub['payment_id'] = notification.object.id
                sub['datetime_expire'] = new_datetime_expire.strftime(DATETIME_FORMAT)
                break
        save_user(user_id, user_data)

        remove_payment(notification.object.id)
    except Exception as e:
        wakeup_admins(f"Ошибка продления подписки {user_id=} {notification.object.id=}")
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
            await bot.send_message(user_id, get_canceled_pay_message(),
                                   reply_markup=get_canceled_pay_keyboard(sub_name, sub))

            remove_payment(notification.object.id)

            return web.Response(status=200)

        else:
            print('Unrecognized event type')
    except Exception as e:
        traceback.print_exc()
        wakeup_admins(f"Ошибка обработки webhook")
        logging.error(f"Error processing payment webhook: {str(e)}")
        return web.Response(status=500)


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

# TODO: Инструкции
# TODO: рефералка
