from datetime import timedelta

subscriptions = {
    # Подписка для тестирования
    'testday_1': {'name': 'VPN на день (тестовая подписка)', 'price': 20, 'period': timedelta(days=1),
                  'devices': 1},

    # Планы
    'try_period': {'name': 'VPN на день (1 устройство)', 'price': 0, 'period': timedelta(days=1),
                   'devices': 1, 'speed': 50},
    'month_1': {'name': 'VPN на месяц (1 устройство)', 'price': 100, 'period': timedelta(days=31),
                'devices': 1, 'speed': 50},
    'month_2': {'name': 'VPN на месяц (2 устройства)', 'price': 150, 'period': timedelta(days=31),
                'devices': 2, 'speed': 50},
    'month_3': {'name': 'VPN на месяц (3 устройства)', 'price': 200, 'period': timedelta(days=31),
                'devices': 3, 'speed': 50},
    'year_1': {'name': 'VPN на год (1 устройство)', 'price': 1000, 'period': timedelta(days=365),
               'devices': 1, 'speed': 70},
    'year_2': {'name': 'VPN на год (2 устройства)', 'price': 1500, 'period': timedelta(days=365),
               'devices': 2, 'speed': 70},
    'year_3': {'name': 'VPN на год (3 устройства)', 'price': 2000, 'period': timedelta(days=365),
               'devices': 3, 'speed': 70},
}
