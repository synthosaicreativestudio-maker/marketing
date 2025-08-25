"""
Конфигурация проекта Marketing Bot
Централизованные настройки и константы
"""

import os
from typing import List

# Google Sheets конфигурация
SHEET_COLUMNS = {
    'CODE': 1,           # Колонка A - код партнера
    'PHONE': 2,          # Колонка B - телефон
    'FIO': 3,            # Колонка C - ФИО
    'AUTH_STATUS': 4,    # Колонка D - статус авторизации
    'TELEGRAM_ID': 5,    # Колонка E - Telegram ID
    'PARTNER_STATUS': 6, # Колонка F - статус партнера
}

TICKET_COLUMNS = {
    'CODE': 1,           # Колонка A - код партнера
    'PHONE': 2,          # Колонка B - телефон
    'FIO': 3,            # Колонка C - ФИО
    'TELEGRAM_ID': 4,    # Колонка D - Telegram ID
    'TICKETS': 5,        # Колонка E - обращения
    'STATUS': 6,         # Колонка F - статус
    'LAST_UPDATED': 7,   # Колонка G - время обновления
}

# Разделы меню
SECTIONS = [
    'Агрегаторы',
    'Контент',
    'Финансы',
    'Технические проблемы',
    'Дизайн и материалы',
    'Регламенты и обучение',
    'Акции и мероприятия',
    'Аналитика',
    'Связаться со специалистом'
]

# Настройки авторизации
AUTH_CONFIG = {
    'MAX_ATTEMPTS': 5,
    'BLOCK_DURATIONS': [86400, 432000, 2592000],  # 1 день, 5 дней, 30 дней
    'CACHE_TTL': 30,  # секунды
    'USER_CACHE_TTL': 300,  # 5 минут
}

# Настройки OpenAI
OPENAI_CONFIG = {
    'MAX_CONCURRENT': 3,
    'MAX_RETRY': 2,
    'BACKOFF_BASE': 0.8,
    'DEFAULT_MODEL': 'gpt-3.5-turbo',
}

# URL веб-приложений
WEB_APP_URLS = {
    'MAIN': 'https://synthosaicreativestudio-maker.github.io/marketing/',
    'MENU': 'https://synthosaicreativestudio-maker.github.io/marketing/mini_app.html',
}

# Статусы тикетов
TICKET_STATUSES = {
    'IN_PROGRESS': 'в работе',
    'COMPLETED': 'выполнено',
    'PENDING': 'ожидает',
}

# Цвета для форматирования Google Sheets
SHEET_COLORS = {
    'COMPLETED': {'red': 0, 'green': 0.8, 'blue': 0},      # Зеленый
    'IN_PROGRESS': {'red': 0.8, 'green': 0, 'blue': 0},    # Красный
    'DEFAULT': {'red': 1, 'green': 1, 'blue': 1},          # Белый
}

def get_env_or_default(key: str, default: str) -> str:
    """Получает значение из переменной окружения или возвращает значение по умолчанию"""
    return os.getenv(key, default)

def get_web_app_url(key: str = 'MAIN') -> str:
    """Получает URL веб-приложения по ключу"""
    return WEB_APP_URLS.get(key, WEB_APP_URLS['MAIN'])

def get_sheet_column(column_type: str, is_ticket: bool = False) -> int:
    """Получает номер колонки по типу"""
    columns = TICKET_COLUMNS if is_ticket else SHEET_COLUMNS
    return columns.get(column_type, 1)

def get_ticket_status(status_type: str) -> str:
    """Получает статус тикета по типу"""
    return TICKET_STATUSES.get(status_type, TICKET_STATUSES['PENDING'])

def get_sheet_color(status: str) -> dict:
    """Получает цвет для статуса"""
    status_lower = status.lower()
    if any(word in status_lower for word in ['выполнено', 'completed', 'done']):
        return SHEET_COLORS['COMPLETED']
    elif any(word in status_lower for word in ['в работе', 'work', 'open', 'in progress']):
        return SHEET_COLORS['IN_PROGRESS']
    return SHEET_COLORS['DEFAULT']


