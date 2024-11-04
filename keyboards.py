from aiogram import types
from aiogram.types import InlineKeyboardMarkup

from subscriptions import subscriptions


# Блок приветствие

def get_welcome_message():
    return f"""
Привет! 🌟 Добро пожаловать в наш VPN-бот! 🌐

Безлимитный трафик и время подключения

Защити свою онлайн-активность и получи доступ к заблокированным сайтам с легкостью. 🚀 
Просто выбери нужный режим работы и наслаждайся безопасным интернет-серфингом! 🔒

Если у тебя возникнут вопросы, просто напиши мне @kovanoFFFreelance. Я всегда на связи! 🤖💬

Вот наши расценки: 👇✨

⚪️ 1 устройство: <b>{subscriptions['month_1']['price']}₽</b>/месяц
🔵 2 устройства: <b>{subscriptions['month_2']['price']}₽</b>/месяц
🔴 З устройства: <b>{subscriptions['month_3']['price']}₽</b>/месяц

Цена за год (х10), ну вы поняли, cкидочка 20%😉
"""


def get_welcome_keyboard():
    button1 = types.InlineKeyboardButton(text="Получить пробный период (1 день)", callback_data="try_period")
    button2 = types.InlineKeyboardButton(text="Приобрести подписку", callback_data="get_sub")
    return InlineKeyboardMarkup(inline_keyboard=[[button1], [button2]])


# Блок список подписок

def get_subs_message():
    return ["""
Выбирайте удобный план и наслаждайтесь безопасным интернет-серфингом! 🌐

✅ Безопасные платежи через ЮКасса
✅ Гарантия возврата средств в течение 3-х дней после приобретения подписки 

📅 Ежемесячные подписки:
""", "🗓️ Годовые подписки (✅ Экономия 20%):"]


def get_subs_keyboard():
    month_1 = types.InlineKeyboardButton(text=f"1 устройство - {subscriptions['month_1']['price']}₽",
                                         callback_data="month_1")
    month_2 = types.InlineKeyboardButton(text=f"2 устройство - {subscriptions['month_2']['price']}₽",
                                         callback_data="month_2")
    month_3 = types.InlineKeyboardButton(text=f"3 устройство - {subscriptions['month_3']['price']}₽",
                                         callback_data="month_3")

    year_1 = types.InlineKeyboardButton(text=f"1 устройство - {subscriptions['year_1']['price']}₽",
                                        callback_data="year_1")
    year_2 = types.InlineKeyboardButton(text=f"2 устройство - {subscriptions['year_2']['price']}₽",
                                        callback_data="year_2")
    year_3 = types.InlineKeyboardButton(text=f"3 устройство - {subscriptions['year_3']['price']}₽",
                                        callback_data="year_3")

    return [
        InlineKeyboardMarkup(inline_keyboard=[[month_1], [month_2], [month_3]]),
        InlineKeyboardMarkup(inline_keyboard=[[year_1], [year_2], [year_3]])
    ]


# Блок оплаты

def get_pay_message():
    return """
🛍️ Отлично! Вот ваша ссылка на оплату: ✨"""


def get_pay_keyboard(amount, url):
    button1 = types.InlineKeyboardButton(text=f"Оплатить {amount}₽", url=url)
    return InlineKeyboardMarkup(inline_keyboard=[[button1]])


# Успешная оплата

def get_success_pay_message(config_url):
    return f"""
✅ Супер! Вот ваши данные для VPN подключения: 🌐

{config_url}"""


def get_success_pay_keyboard():
    button1 = types.InlineKeyboardButton(text="Инструкция для IOS", callback_data="instruction_ios")
    button2 = types.InlineKeyboardButton(text="Инструкция для Android", callback_data="instruction_android")
    button3 = types.InlineKeyboardButton(text="Инструкция для MacOs", callback_data="instruction_macos")
    button4 = types.InlineKeyboardButton(text="Инструкция для Windows", callback_data="instruction_windows")
    return InlineKeyboardMarkup(inline_keyboard=[[button1], [button2], [button3], [button4]])
