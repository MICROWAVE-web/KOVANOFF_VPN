# Токер телеграмм
import pytz
from aiogram import Router
from decouple import config
from yookassa import Configuration

API_TOKEN = config('API_TOKEN')

# Id администраторов
ADMINS = config('ADMINS').split(',')

# ЮКасса
TEST_PAYMETNS = bool(int(config('TEST_PAYMENTS')))
if TEST_PAYMETNS:
    YOOKASSA_SHOP_ID = config('TEST_YOOKASSA_SHOP_ID')
    YOOKASSA_SECRET_KEY = config('TEST_YOOKASSA_SECRET_KEY')
else:
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

# Кое-т для напоминания
K_remind = 0.85

# Лимит активных подписок
ACTIVE_COUNT_SUB_LIMIT = 3

