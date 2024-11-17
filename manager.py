import json
import os

# Путь к файлу JSON
DATA_FILE = 'data_files/users.json'
PAYMENTS_FILE = 'data_files/payments.json'

# Инициализация JSON-файла, если он не существует
if not os.path.exists(DATA_FILE):
    with open(DATA_FILE, 'w') as file:
        json.dump({}, file)

# Инициализация JSON-файла, если он не существует
if not os.path.exists(PAYMENTS_FILE):
    with open(PAYMENTS_FILE, 'w') as file:
        json.dump({}, file)


def count_active_subscriptions(user_id):
    user_id = str(user_id)
    user_data = get_user_data(user_id)
    if user_data is None:
        return 0
    subscriptions = user_data.get('subscriptions')
    if subscriptions is None:
        return 0
    active_subscriptions = 0
    for subscription in subscriptions:
        if subscription['active']:
            active_subscriptions += 1
    return active_subscriptions


def load_users():
    with open(DATA_FILE, 'r', encoding='utf-8') as file:
        return json.load(file)


def get_users_id():
    return list(load_users().keys())


def save_user(user_id, user_data):
    user_id = str(user_id)
    users = load_users()
    users[user_id] = user_data
    with open(DATA_FILE, 'w') as file:
        json.dump(users, file, indent=4, ensure_ascii=False)


def add_user(user_id, user_data):
    user_id = str(user_id)
    users = load_users()
    if user_id not in users.keys():
        save_user(user_id, user_data)
        print(f'Пользователь {user_id} добавлен.')
        return True
    else:
        print(f'Пользователь {user_id} уже существует.')
        return False


def get_user_data(user_id):
    user_id = str(user_id)
    users = load_users()
    return users.get(user_id)


def get_user_payments(user_id):
    user_id = str(user_id)
    user_data = get_user_data(user_id)
    payments = []
    if user_data:
        for sub in user_data['subscriptions']:
            payments.append(sub['payment_id'])
        return payments
    return None


def load_payments():
    with open(PAYMENTS_FILE, 'r', encoding='utf-8') as file:
        return json.load(file)


def get_payment(payment_id):
    payment_id = str(payment_id)
    payments = load_payments()
    return payments.get(payment_id)


def add_payment(payment_id, payment_data):
    payment_id = str(payment_id)
    payments = load_payments()
    print(payments.keys())
    if payment_id not in payments.keys():
        payments[payment_id] = payment_data
        with open(PAYMENTS_FILE, 'w') as file:
            json.dump(payments, file, indent=4, ensure_ascii=False)
        print(f'Платеж {payment_id} добавлен.')
        return True
    else:
        print(f'Платеж {payment_id} уже существует.')
        return False


def remove_payment(payment_id):
    payment_id = str(payment_id)
    payments = load_payments()
    del payments[payment_id]
    with open(PAYMENTS_FILE, 'w') as file:
        json.dump(payments, file, indent=4, ensure_ascii=False)


# Пример использования
if __name__ == "__main__":
    r = get_users_id()
    print(r)
    # add_payment(1, {1: 2})
    # remove_payment(1)
