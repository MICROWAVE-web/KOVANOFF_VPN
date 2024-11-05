import asyncio
import io
import logging
import ssl
import sys
import time
import traceback
import uuid
from datetime import datetime, timedelta

import qrcode
from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, BufferedInputFile
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web
from celery import Celery
from decouple import config
from yookassa import Payment, Refund, Configuration
from yookassa.domain.notification import WebhookNotification

from keyboards import *
from manager import *
from panel_3xui import login, add_client, get_client_url

API_TOKEN = config('API_TOKEN')

YOOKASSA_SHOP_ID = config('YOOKASSA_SHOP_ID')
YOOKASSA_SECRET_KEY = config('YOOKASSA_SECRET_KEY')

BASE_WEBHOOK_URL = f'https://{config("WEBHOOK_DOMAIN")}:443'
WEBHOOK_PATH = '/webhook'
PAYMENT_WEBHOOK_PATH = '/payment-webhook'

WEBAPP_HOST = '127.0.0.1'
WEBAPP_PORT = int(config("WEBAPP_PORT"))

WEBHOOK_SECRET = config('WEBHOOK_SECRET')

WEBHOOK_SSL_CERT = config('WEBHOOK_SSL_CERT')
WEBHOOK_SSL_PRIV = config('WEBHOOK_SSL_PRIV')

DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"
# Роутер
router = Router()

# Режим проограммы
mode = config('MODE')

# Настройка конфигурации ЮKassa
Configuration.account_id = YOOKASSA_SHOP_ID
Configuration.secret_key = YOOKASSA_SECRET_KEY

# Инициализация Celery
app = Celery('tasks', broker='redis://localhost:6379/0')


@app.task
def send_message(user_id, text):
    async def _send_message():
        await bot.send_message(user_id, text)

    from asyncio import run
    run(_send_message())


async def schedule_message(user_id, text, delay):
    send_message.apply_async((user_id, text), countdown=delay)


@router.message(CommandStart())
async def send_welcome(message: types.Message):
    await message.reply(get_welcome_message(), reply_markup=get_welcome_keyboard())


@router.message(Command('delay'))
async def test_send_message(message: types.Message):
    await schedule_message(message.from_user.id, 'NIGA!', 30)
    await message.reply("Сообщение будет отправлено через 30 секунд.")


@router.callback_query(F.data == 'get_sub')
async def get_sub(call: CallbackQuery, state: FSMContext):
    await call.message.answer(text=get_subs_message()[0], reply_markup=get_subs_keyboard()[0])
    await call.message.answer(text=get_subs_message()[1], reply_markup=get_subs_keyboard()[1])
    await state.clear()


@router.callback_query(F.data.startswith("month_") | F.data.startswith("year_"))
async def process_subscribe(call: CallbackQuery, state: FSMContext):
    subscription = subscriptions.get(call.data)
    if subscription:
        payment = Payment.create({
            "amount": {
                "value": str(subscription['price']),
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
            }
        )

        await call.message.answer(text=get_pay_message(), reply_markup=get_pay_keyboard(subscription['price'],
                                                                                        payment.confirmation.confirmation_url))
    else:
        await call.message.answer("Неверная команда. Напишите /start")
    await state.clear()


@router.message(Command('my_subs'))
async def my_subs(message: types.Message):
    pass


@router.message(Command('refund'))
async def process_refund(message: types.Message):
    for payment_id, info in payments.items():
        if info['user_id'] == message.from_user.id:
            elapsed = datetime.now() - info['timestamp']
            if elapsed <= timedelta(days=2):
                refund = Refund.create({
                    "amount": {
                        "value": "2.00",
                        "currency": "RUB"
                    },
                    "payment_id": "21740069-000f-50be-b000-0486ffbf45b0"
                })
                await message.reply(f"Возврат средств за {info['subscription']['name']} выполнен.")
                del payments[payment_id]
                return
            else:
                await message.reply("Возврат возможен только в течение 2 дней после оплаты.")
                return


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

            user_data = get_user_data(user_id)
            panel_uuid = str(uuid.uuid4())

            api = login()
            user_delta = subscriptions[payment['subscription']]['period']
            devices_count = subscriptions[payment['subscription']]['devices']
            add_client(api, panel_uuid, devices_count, user_delta)
            config_url = get_client_url(api, panel_uuid)

            if user_data is None:
                add_user(user_id, {
                    'subscriptions': [
                        {
                            'payment_id': notification.object.id,
                            'subscription': payment['subscription'],
                            'datetime_operation': datetime.now().strftime(DATETIME_FORMAT),
                            'datetime_expire': (datetime.now() + user_delta).strftime(DATETIME_FORMAT),
                            'panel_uuid': panel_uuid
                        }
                    ],
                    'last_refund': None
                })
            else:
                user_data['subscriptions'].append(
                    {
                        'payment_id': notification.object.id,
                        'subscription': payment['subscription'],
                        'datetime_operation': datetime.now().strftime(DATETIME_FORMAT),
                        'datetime_expire': (datetime.now() + user_delta).strftime(DATETIME_FORMAT),
                        'panel_uuid': panel_uuid
                    }
                )
                save_user(user_id, user_data)

            remove_payment(notification.object.id)

            img = qrcode.make(config_url)
            byte_arr = io.BytesIO()
            img.save(byte_arr, format='PNG')
            byte_arr.seek(0)

            await bot.send_photo(user_id, photo=BufferedInputFile(file=byte_arr.read(), filename="qrcode.png"),
                                 caption=get_success_pay_message(config_url),
                                 reply_markup=get_success_pay_keyboard())

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

        elif notification.event == 'refund.succeeded':
            logging.info(f"Refund succeeded for payment id: {notification.object.id}")

            payment = get_payment(notification.object.id)
            # Уведомить об успешном возврате
            remove_payment(notification.object.id)

            return web.Response(status=200)

        else:
            print('Unrecognized event type')
    except Exception as e:
        traceback.print_exc()
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

    dp.include_router(router)

    bot = Bot(token=API_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))

    if mode == "local":
        # Локальный запуск бота
        asyncio.run(local_startup(bot))
    else:

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
