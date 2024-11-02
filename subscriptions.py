from datetime import timedelta

subscriptions = {
    'month_1': {'name': 'Подписка VPN на месяц (1 устройство)', 'price': 50, 'period': timedelta(days=30)},
    'month_2': {'name': 'Подписка VPN на месяц (2 устройства)', 'price': 75, 'period': timedelta(days=30)},
    'month_3': {'name': 'Подписка VPN на месяц (3 устройства)', 'price': 100, 'period': timedelta(days=30)},
    'year_1': {'name': 'Подписка VPN на год (1 устройство)', 'price': 500, 'period': timedelta(days=365)},
    'year_2': {'name': 'Подписка VPN на год (2 устройства)', 'price': 750, 'period': timedelta(days=365)},
    'year_3': {'name': 'Подписка VPN на год (3 устройства)', 'price': 1000, 'period': timedelta(days=365)},
}
