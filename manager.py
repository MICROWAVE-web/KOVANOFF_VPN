import json
import os

# Путь к файлу JSON
DATA_FILE = 'users.json'

# Инициализация JSON-файла, если он не существует
if not os.path.exists(DATA_FILE):
    with open(DATA_FILE, 'w') as file:
        json.dump({}, file)


def load_users():
    with open(DATA_FILE, 'r', encoding='utf-8') as file:
        return json.load(file)


def save_user(user_id, user_data):
    data = load_users()
    data[user_id] = user_data
    with open(DATA_FILE, 'w') as file:
        json.dump(data, file, indent=4, ensure_ascii=False)


def add_user(user_id, user_data):
    users = load_users()
    if user_id not in users.keys():
        save_user(user_id, user_data)
        print(f'Пользователь {user_id} добавлен.')
        return True
    else:
        print(f'Пользователь {user_id} уже существует.')
        return False


def get_user(user_id):
    users = load_users()
    return users.get(user_id)


# Пример использования
if __name__ == "__main__":
    add_user('123456', 'month', '2024-10-31')
    print(get_user('123456'))
    print(get_user('1234567'))
