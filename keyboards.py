import telebot
from aiogram import types
from aiogram.types import InlineKeyboardMarkup

from headers import TEST_PAYMETNS
from subscriptions import subscriptions


# Блок приветствие

def get_welcome_message():
    return f"""
Привет! 🌟 Добро пожаловать в наш VPN-бот! 🌐

Безлимитный трафик и время подключения

Польский сервер 🇵🇱

Защити свою онлайн-активность и получи доступ к заблокированным сайтам с легкостью. 🚀 
Просто выбери нужный режим работы и наслаждайся безопасным интернет-серфингом! 🔒

Если у тебя возникнут вопросы, просто напиши мне @kovanoFFFreelance. Я всегда на связи! 🤖💬

Вот наши расценки: 👇✨

⚪️ 1 устройство: <b>{subscriptions['month_1']['price']}₽</b>/месяц
🔵 2 устройства: <b>{subscriptions['month_2']['price']}₽</b>/месяц
🔴 З устройства: <b>{subscriptions['month_3']['price']}₽</b>/месяц

Цена за год (х10), ну вы поняли, cкидочка 20%😉

Ps. скидка до 15% за приглашённого по реферальной ссылке (+3% за каждого оформившего подписку) 

<a href='https://maptap.ru/user_agreement'>Пользовательское соглашение</a>
"""


def get_welcome_keyboard():
    button1 = types.InlineKeyboardButton(text="Получить пробный период (1 день)", callback_data="try_period")
    button2 = types.InlineKeyboardButton(text="Приобрести подписку", callback_data="get_sub")
    return InlineKeyboardMarkup(inline_keyboard=[[button1], [button2]])


# Блок список подписок

def get_subs_message(sale: int = 0):
    return [f"""
Выбирайте удобный план и наслаждайтесь безопасным интернет-серфингом! 🌐

✅ Безопасные платежи через ЮКасса
✅ Гарантия возврата средств в течение 3-х дней после приобретения подписки 

{f'🔖 Ваша скидка: {sale}%' if sale else ''}
📅 Ежемесячные подписки:
""", "🗓️ Годовые подписки (✅ Экономия 20%):"]


def get_subs_keyboard(sale: int = 0):
    testday_1 = types.InlineKeyboardButton(
        text=f"1 устройство (тестовая подписка) - {subscriptions['testday_1']['price'] * (100 - sale) / 100}₽",
        callback_data="testday_1")

    month_1 = types.InlineKeyboardButton(
        text=f"1 устройство - {subscriptions['month_1']['price'] * (100 - sale) / 100}₽",
        callback_data="month_1")
    month_2 = types.InlineKeyboardButton(
        text=f"2 устройство - {subscriptions['month_2']['price'] * (100 - sale) / 100}₽",
        callback_data="month_2")
    month_3 = types.InlineKeyboardButton(
        text=f"3 устройство - {subscriptions['month_3']['price'] * (100 - sale) / 100}₽",
        callback_data="month_3")

    year_1 = types.InlineKeyboardButton(text=f"1 устройство - {subscriptions['year_1']['price'] * (100 - sale) / 100}₽",
                                        callback_data="year_1")
    year_2 = types.InlineKeyboardButton(text=f"2 устройство - {subscriptions['year_2']['price'] * (100 - sale) / 100}₽",
                                        callback_data="year_2")
    year_3 = types.InlineKeyboardButton(text=f"3 устройство - {subscriptions['year_3']['price'] * (100 - sale) / 100}₽",
                                        callback_data="year_3")

    return [
        InlineKeyboardMarkup(inline_keyboard=[[month_1], [month_2], [month_3]]),
        InlineKeyboardMarkup(inline_keyboard=[[year_1], [year_2], [year_3]])
    ] if not TEST_PAYMETNS else [
        InlineKeyboardMarkup(inline_keyboard=[[testday_1]]),
        InlineKeyboardMarkup(inline_keyboard=[])
    ]


# Блок оплаты

def get_pay_message(sale):
    return f"""
🛍️ Отлично! Вот ваша ссылка на оплату: ✨
{f'Ваша скидка: {sale}%' if sale > 0 else ''}"""


def get_pay_keyboard(amount, url):
    button1 = types.InlineKeyboardButton(text=f"Оплатить {amount}₽", url=url)
    return InlineKeyboardMarkup(inline_keyboard=[[button1]])


# Успешная оплата

def get_success_pay_message(config_url):
    return f"""
✅ Супер! Вот ваши данные для VPN подключения: 🌐

<blockquote>{config_url}</blockquote>

Спасибо за выбор Kovanoff VPN 🍀"""


def get_success_pay_keyboard():
    button1 = types.InlineKeyboardButton(text="Инструкция для всех платформ", callback_data="instruction")
    return InlineKeyboardMarkup(inline_keyboard=[[button1]])


# Отмена оплаты

def get_canceled_pay_message():
    return f"""
❌ Упс! оплата не прошла, попробуйте снова:
"""


def get_canceled_pay_keyboard(again_text, again_callback):
    button1 = types.InlineKeyboardButton(text=again_text, callback_data=again_callback)
    return InlineKeyboardMarkup(inline_keyboard=[[button1]])


# Список подписок

def get_empty_subscriptions_message():
    return f"""
❌ У вас нет подписок 🥺
"""


def get_actual_subscriptions_message(active_subs, inactive_subs):
    active_subs_text = []
    for sub in active_subs:
        active_subs_text.append(f"""<blockquote>{subscriptions[sub['subscription']]['name']}        
От: {sub['datetime_operation']}
До: {sub['datetime_expire']}</blockquote>""")

    inactive_subs_text = []
    for sub in inactive_subs:
        inactive_subs_text.append(f"""<blockquote>{subscriptions[sub['subscription']]['name']}        
От: {sub['datetime_operation']}
До: {sub['datetime_expire']}</blockquote>""")

    return f"""
📋 Вот список всех ваших VPN подписок: 🌐

{"🟢 Активные подписки:" + ' '.join(active_subs_text) if len(active_subs_text) > 0 else ""}
{"🔴 Истёкшие подписки:" + ' '.join(inactive_subs_text) if len(inactive_subs_text) > 0 else ""}
Ключи активных подписок:
"""


def get_active_subscriptions_keyboard(active_subs):
    button_list = [
        [types.InlineKeyboardButton(text=f"{subscriptions[sub['subscription']]['name']} До: {sub['datetime_expire']}",
                                    callback_data=f"get_info_{sub['panel_uuid']}")] for sub in active_subs
    ]
    return InlineKeyboardMarkup(inline_keyboard=button_list)


# Подписка окончена/заканчивается

def get_cancel_subsciption():
    return """
⛔ К сожалению ваша подписка закончилась. Поспешите продлить доступ к интернету без ограничений 🚀"""


def get_remind_message(days_before_expr):
    return f"""
❗ Внимание, ваша подписка закончится через {days_before_expr} дня. Поспешите продлить доступ к интернету без ограничений 🚀"""


def get_continue_cancell_message():
    return f"""
⛔ К сожалению ваша подписка закончилась. Продлить её не получиться. Вы всегда можете приобрести новую 🚀"""


def get_cancel_keyboard():
    markup = telebot.types.InlineKeyboardMarkup()
    button = telebot.types.InlineKeyboardButton(text="Приобрести подписку", callback_data="get_sub")
    markup.add(button)
    return markup


def get_cancel_keyboard_aiogram():
    button = types.InlineKeyboardButton(text="Приобрести подписку", callback_data="get_sub")
    return InlineKeyboardMarkup(inline_keyboard=[[button]])


def get_continue_keyboard(panel_uuid):
    markup = telebot.types.InlineKeyboardMarkup()
    button = telebot.types.InlineKeyboardButton(
        text="Продлить подписку",
        callback_data=f"continue_{panel_uuid}"
    )
    markup.add(button)
    return markup


# Продление подписки

def get_success_continue_message(exp_date):
    return f"""
Подписка успешно продлена! ✅
Дата окончания подписки: {exp_date}"""


# Пробная подписка
def get_cancel_try_period_message():
    return """
К сожалению воспользоваться пробным периодом можно только 1 раз 😁. Рекомендуем приобрести подписку"""


# Реферал

def get_ref_link_message(link):
    return f"🔗 Ваша реф. ссылка {link}"


def get_sale_limit_message(sale):
    return f"""
По вашей ссылке приобрели подписку. 💲 
Ваша скидка: {sale}% (Максимум.) 🔝"""


def get_sale_increase_message(sale):
    return f"""
По вашей ссылке приобрели подписку. 💲 
Ваша скидка: {sale}% 📈"""


# Технические работы
def get_service_working_message():
    return """
🚧 Внимание! В данный момент проводятся технические работы 🛠️. Наш бот временно недоступен ⏳. Мы прилагаем все усилия, чтобы вернуться как можно скорее! 🔧

Спасибо за ваше терпение и понимание 🙏"""


def get_subs_limit_message(limit):
    return f"""
⚠️ У вас не может быть больше {limit} активных подписок! 🖐️

Пожалуйста, дождитесь окончания одной из текущих подписок, чтобы добавить новую 💳"""


def get_wrong_command_message():
    return """
⚠️️ У вас нет прав, чтобы использовать эту команду!"""
