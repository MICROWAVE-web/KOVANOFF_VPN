import asyncio
import logging
import ssl
import sys
import time
import uuid
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web
from decouple import config
from yookassa import Payment, Refund, Configuration
from yookassa.domain.notification import WebhookNotification

from keyboards import *

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

# Роутер
router = Router()

# Режим проограммы
mode = config('MODE')

# Настройка конфигурации ЮKassa
Configuration.account_id = YOOKASSA_SHOP_ID
Configuration.secret_key = YOOKASSA_SECRET_KEY

payments = {}


@router.message(CommandStart())
async def send_welcome(message: types.Message):
    await message.reply(get_welcome_message(), reply_markup=get_welcome_keyboard())


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
        payments[payment.id] = {
            'user_id': call.from_user.id,
            'subscription': subscription,
            'timestamp': datetime.now()
        }
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
            return web.Response(status=200)

        elif notification.event == 'payment.canceled':
            logging.info(f"Payment canceled for payment id: {notification.object.id}")
            return web.Response(status=200)

        elif notification.event == 'refund.succeeded':
            logging.info(f"Refund succeeded for payment id: {notification.object.id}")
            return web.Response(status=200)

        else:
            print('Unrecognized event type')
    except Exception as e:
        logging.error(f"Error processing payment webhook: {str(e)}")
        return web.Response(status=500)


async def on_startup(bot: Bot) -> None:
    # But if you have a valid SSL certificate, you SHOULD NOT send it to Telegram servers.
    await bot.set_webhook(
        f"{BASE_WEBHOOK_URL}{WEBHOOK_PATH}",
    )
    time.sleep(3)
    print(await bot.get_webhook_info())


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
