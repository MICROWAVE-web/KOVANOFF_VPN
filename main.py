import logging
import ssl
import sys
import uuid
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, types, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.types import FSInputFile
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web
from decouple import config
from yookassa import Payment, Refund, Configuration
from yookassa.domain.notification import WebhookNotification

API_TOKEN = config('API_TOKEN')

YOOKASSA_SHOP_ID = config('YOOKASSA_SHOP_ID')
YOOKASSA_SECRET_KEY = config('YOOKASSA_SECRET_KEY')

BASE_WEBHOOK_URL = f'https://{config("WEBHOOK_DOMAIN")}'
WEBHOOK_PATH = '/webhook'
PAYMENT_WEBHOOK_PATH = '/payment-webhook'

WEBAPP_HOST = '127.0.0.1'
WEBAPP_PORT = int(config("WEBAPP_PORT"))

WEBHOOK_SECRET = config('WEBHOOK_SECRET')

WEBHOOK_SSL_CERT = config('WEBHOOK_SSL_CERT')
WEBHOOK_SSL_PRIV = config('WEBHOOK_SSL_PRIV')

# Роутер
router = Router()

# Настройка логирования
logging.basicConfig(level=logging.INFO, stream=sys.stdout)

# Настройка конфигурации ЮKassa
Configuration.account_id = YOOKASSA_SHOP_ID
Configuration.secret_key = YOOKASSA_SECRET_KEY

subscriptions = {
    'month_1': {'name': 'Подписка VPN на месяц (1 устройство)', 'price': 50, 'period': timedelta(days=30)},
    'month_2': {'name': 'Подписка VPN на месяц (2 устройства)', 'price': 75, 'period': timedelta(days=30)},
    'month_3': {'name': 'Подписка VPN на месяц (3 устройства)', 'price': 100, 'period': timedelta(days=30)},
    'year_1': {'name': 'Подписка VPN на год (1 устройство)', 'price': 500, 'period': timedelta(days=365)},
    'year_2': {'name': 'Подписка VPN на год (2 устройства)', 'price': 750, 'period': timedelta(days=365)},
    'year_3': {'name': 'Подписка VPN на год (3 устройства)', 'price': 1000, 'period': timedelta(days=365)},
}

payments = {}


@router.message(Command('start'))
async def send_welcome(message: types.Message):
    await message.reply("""
Привет! Выберите подписку: 
/subscribe_month_1
/subscribe_month_2
/subscribe_month_3
/subscribe_year_1
/subscribe_year_2
/subscribe_year_3
    """)


@router.message(F.text.startswith("/subscribe_"))
async def process_subscribe(message: types.Message):
    command = message.text.lstrip('/')
    subscription = subscriptions.get(command.split('_', 1)[1])
    if subscription:
        payment = Payment.create({
            "amount": {
                "value": str(subscription['price']),
                "currency": "RUB"
            },
            "confirmation": {
                "type": "redirect",
                "return_url": "https://google.com"
            },
            "capture": True,
            "description": subscription['name']
        }, uuid.uuid4())
        payments[payment.id] = {
            'user_id': message.from_user.id,
            'subscription': subscription,
            'timestamp': datetime.now()
        }
        await message.reply(f"Оплатите подписку: {payment.confirmation.confirmation_url}")
    else:
        await message.reply("Неверная команда. Напишите /start")


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
        certificate=FSInputFile(WEBHOOK_SSL_CERT),
        secret_token=WEBHOOK_SECRET,
    )


if __name__ == '__main__':
    dp = Dispatcher()

    dp.include_router(router)

    dp.startup.register(on_startup)

    bot = Bot(token=API_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))

    app = web.Application()
    app.router.add_post(PAYMENT_WEBHOOK_PATH, payment_webhook_handler)

    webhook_requests_handler = SimpleRequestHandler(
        dispatcher=dp,
        bot=bot,
        secret_token=config("WEBHOOK_SECRET"),
    )
    # Register webhook handler on application
    webhook_requests_handler.register(app, path=WEBHOOK_PATH)

    # Mount dispatcher startup and shutdown hooks to aiohttp application
    setup_application(app, dp, bot=bot)

    # Generate SSL context
    # context = ssl.SSLContext(ssl.PROTOCOL_TLSv1_2)
    # context.load_cert_chain(WEBHOOK_SSL_CERT, WEBHOOK_SSL_PRIV)

    # And finally start webserver
    web.run_app(app, host=WEBAPP_HOST, port=WEBAPP_PORT)
