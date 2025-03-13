# VPN приложение на удаленный сервер основанный на 3XUI + Телеграмм бот для монитизации VPN бота + ЮКасса
Проект был реализован с целью создать стабильный VPN для огрниченного числа людей, с возможностью монитизировать услугу выдачи VPN при помощи сервиса ЮКасса. А также реализована небольшая landing страница

## Содержание
- [Технологии](#технологии)
- [Начало работы](#начало-работы)
- [Команда проекта](#команда-проекта)

## Технологии
- [3XUI](https://github.com/MHSanaei/3x-ui)
- [ЮКасса API](https://yookassa.ru/developers)
- [Aiogram](https://aiogram.dev/)

## Начало работы

### Требования
Для установки и запуска проекта, необходим [Python](https://www.python.org/) v3.10

Клонируйте и установите зависимости:
```sh
$ pip install -r requirements.txt
```

Настройте .env файл:

```
# Телаграмм бот токен
API_TOKEN=0000:abcabcabc

TEST_PAYMENTS=1

# Юкасса
TEST_YOOKASSA_SHOP_ID=00000
TEST_YOOKASSA_SECRET_KEY=test_abc123123123

YOOKASSA_SHOP_ID=482736
YOOKASSA_SECRET_KEY=live_abc123123123

#WEBHOOK для ЮКассы
WEBAPP_PORT=800

WEBHOOK_DOMAIN=domain.com
WEBHOOK_SECRET=supersecret
WEBHOOK_SSL_CERT=/etc/letsencrypt/live/DOMAIN/cert.pem
WEBHOOK_SSL_PRIV=/etc/letsencrypt/live/DOMAIN/privkey.pem

# 3x-ui
XUI_HOST=https://mypanel/panel/
XUI_USERNAME=admin
XUI_PASSWORD=supersescret

# local/server
MODE=local

# Id Администратора(-ов) Telegram через запятую 
ADMINS=000000000
```

### Запуск Development сервера
Чтобы запустить сервер для разработки, выполните команду:
```sh
python main.py
```


## Команда проекта
- [Кованов Алексей (Я)](https://t.me/kovanoFFFreelance) — FullStack Engineer

