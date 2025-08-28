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

# Структура колонок для таблицы обращений (новая логика)
TICKET_COLUMNS = {
    'CODE': 1,           # Колонка A - код партнера
    'PHONE': 2,          # Колонка B - телефон
    'FIO': 3,            # Колонка C - ФИО
    'TELEGRAM_ID': 4,    # Колонка D - Telegram ID
    'TICKETS': 5,        # Колонка E - текст_обращений (история)
    'STATUS': 6,         # Колонка F - статус (ручной выбор специалистом)
    'SPECIALIST_REPLY': 7, # Колонка G - поле для ответа специалиста (временное)
    'LAST_UPDATED': 8,   # Колонка H - время последнего обновления
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

# Настройки авторизации удалены

# Настройки OpenAI
OPENAI_CONFIG = {
    'MAX_CONCURRENT': 3,
    'MAX_RETRY': 2,
    'BACKOFF_BASE': 0.8,
    'DEFAULT_MODEL': 'gpt-3.5-turbo',
}

# URL веб-приложений
WEB_APP_URLS = {
    'MAIN': os.getenv('WEB_APP_URL', 'https://synthosaicreativestudio-maker.github.io/marketing/'),
    'SPA_MENU': os.getenv('WEB_APP_MENU_URL', 'https://synthosaicreativestudio-maker.github.io/marketing/spa_menu.html'),
    'AUTH': os.getenv('WEB_APP_AUTH_URL', 'https://synthosaicreativestudio-maker.github.io/marketing/index.html'),
}

# Статусы тикетов (ручной выбор специалистом)
TICKET_STATUSES = {
    'PENDING': 'ожидает',
    'IN_PROGRESS': 'в работе',
    'COMPLETED': 'выполнено',
    'CANCELLED': 'отменено',
    'ON_HOLD': 'приостановлено',
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

def validate_config() -> tuple[bool, list[str]]:
    """Валидирует конфигурацию проекта"""
    errors = []
    
    # Проверяем константы
    if not SECTIONS:
        errors.append('Отсутствуют разделы меню')
    
    if not SUBSECTIONS:
        errors.append('Отсутствуют подразделы')
    
    # Проверяем соответствие разделов и подразделов
    for section in SECTIONS:
        if section in SUBSECTIONS and not SUBSECTIONS[section]:
            errors.append(f'Пустой список подразделов для {section}')
    
    # Проверяем URLы
    for key, url in WEB_APP_URLS.items():
        if not url.startswith(('http://', 'https://')):
            errors.append(f'Некорректный URL для {key}: {url}')
    
    # Проверки авторизации удалены
    
    return len(errors) == 0, errors

# Подпункты для каждого раздела
SUBSECTIONS = {
    'Агрегаторы': [
        'Статус',
        'Проблемы с выгрузкой',
        'Платное продвижение',
        'Ошибки, отклонения и блокировки',
        'Редактирование контента на площадках',
        'Прочие вопросы'
    ],
    'Контент': [
        'Заказ фото/видео съемки',
        'Работа с текстами объявлений',
        'Требования к контенту',
        'Прочие вопросы'
    ],
    'Финансы': [
        'Списания и расходы',
        'Баланс и пополнение',
        'Отчетность',
        'Прочие вопросы'
    ],
    'Технические проблемы': [
        'Доступ к системам',
        'Проблемы с телефонией',
        'Прочие вопросы'
    ],
    'Дизайн и материалы': [
        'Заказ полиграфии',
        'Заказ цифровых материалов',
        'Прочие вопросы'
    ],
}


