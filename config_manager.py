"""
Configuration Manager для Telegram Bot
Реализует лучшие практики конфигурации из технического плана:
- Использование configparser с правильными методами типов
- Поддержка fallback значений
- Валидация конфигурации
- Подстановка переменных окружения
"""

import configparser
import os
import logging
import re
from typing import Dict, Any, Tuple, List

logger = logging.getLogger(__name__)

class ConfigManager:
    """
    Менеджер конфигурации с поддержкой типов и валидации.
    """
    
    def __init__(self, config_file: str = 'config.ini'):
        """
        Инициализация менеджера конфигурации.
        
        Args:
            config_file: Путь к файлу конфигурации
        """
        self.config_file = config_file
        self.config = configparser.ConfigParser()
        self._load_config()
        
    def _load_config(self):
        """
        Загружает конфигурацию из файла с подстановкой переменных окружения.
        """
        if not os.path.exists(self.config_file):
            raise FileNotFoundError(f"Файл конфигурации не найден: {self.config_file}")
        
        # Читаем файл
        with open(self.config_file, 'r', encoding='utf-8') as f:
            config_content = f.read()
        
        # Подставляем переменные окружения
        config_content = self._substitute_env_vars(config_content)
        
        # Парсим конфигурацию
        self.config.read_string(config_content)
        
        logger.info(f"Конфигурация загружена из {self.config_file}")
    
    def _substitute_env_vars(self, content: str) -> str:
        """
        Подставляет переменные окружения в формате ${VAR_NAME}.
        
        Args:
            content: Содержимое конфигурационного файла
            
        Returns:
            Содержимое с подставленными переменными
        """
        def replace_var(match):
            var_name = match.group(1)
            return os.getenv(var_name, f"${{{var_name}}}")  # Оставляем как есть, если не найдено
        
        return re.sub(r'\$\{([^}]+)\}', replace_var, content)
    
    # Telegram Configuration
    def get_telegram_token(self) -> str:
        """Получает токен Telegram бота."""
        return self.config.get('telegram', 'token')
    
    def get_admin_chat_id(self) -> int:
        """Получает ID чата администратора."""
        return self.config.getint('telegram', 'admin_chat_id', fallback=0)
    
    # Google Sheets Configuration
    def get_credentials_path(self) -> str:
        """Получает путь к файлу credentials.json."""
        return self.config.get('google_sheets', 'credentials_path', fallback='credentials.json')
    
    def get_auth_worksheet_name(self) -> str:
        """Получает имя листа авторизации."""
        return self.config.get('google_sheets', 'auth_worksheet_name', fallback='Авторизация')
    
    def get_tickets_worksheet_name(self) -> str:
        """Получает имя листа обращений."""
        return self.config.get('google_sheets', 'tickets_worksheet_name', fallback='Обращения')
    
    def get_sheet_url(self) -> str:
        """Получает URL основной таблицы."""
        return self.config.get('google_sheets', 'sheet_url', fallback='')
    
    def get_tickets_sheet_url(self) -> str:
        """Получает URL таблицы обращений."""
        return self.config.get('google_sheets', 'tickets_sheet_url', fallback='')
    
    # App Settings
    def is_debug_mode(self) -> bool:
        """Проверяет, включен ли режим отладки."""
        return self.config.getboolean('app_settings', 'debug_mode', fallback=False)
    
    def get_max_retries(self) -> int:
        """Получает максимальное количество повторных попыток."""
        return self.config.getint('app_settings', 'max_retries', fallback=3)
    
    def get_monitoring_interval(self) -> float:
        """Получает интервал мониторинга в секундах."""
        return self.config.getfloat('app_settings', 'monitoring_interval', fallback=30.0)
    
    def get_cache_cleanup_interval(self) -> float:
        """Получает интервал очистки кэша в секундах."""
        return self.config.getfloat('app_settings', 'cache_cleanup_interval', fallback=1800.0)
    
    def get_log_file(self) -> str:
        """Получает путь к файлу логов."""
        return self.config.get('app_settings', 'log_file', fallback='bot.log')
    
    # Promotions Configuration
    def get_promotions_sheet_url(self) -> str:
        """Получает URL таблицы акций."""
        return self.config.get('promotions', 'sheet_url', fallback='')
    
    def get_promotions_monitoring_interval(self) -> float:
        """Получает интервал мониторинга акций в секундах."""
        return self.config.getfloat('promotions', 'monitoring_interval', fallback=30.0)
    
    def get_max_description_length(self) -> int:
        """Получает максимальную длину описания акции."""
        return self.config.getint('promotions', 'max_description_length', fallback=300)
    
    # Authentication Settings
    def get_auth_max_attempts(self) -> int:
        """Получает максимальное количество попыток авторизации."""
        return self.config.getint('auth_settings', 'max_attempts', fallback=3)
    
    def get_cache_ttl(self) -> float:
        """Получает время жизни кэша в секундах."""
        return self.config.getfloat('auth_settings', 'cache_ttl', fallback=3600.0)
    
    def get_block_duration(self) -> float:
        """Получает длительность блокировки в секундах."""
        return self.config.getfloat('auth_settings', 'block_duration', fallback=1800.0)
    
    # OpenAI Configuration
    def get_openai_api_key(self) -> str:
        """Получает API ключ OpenAI."""
        return self.config.get('openai', 'api_key', fallback='')
    
    def get_openai_model(self) -> str:
        """Получает модель OpenAI."""
        return self.config.get('openai', 'model', fallback='gpt-4')
    
    def get_openai_max_tokens(self) -> int:
        """Получает максимальное количество токенов для OpenAI."""
        return self.config.getint('openai', 'max_tokens', fallback=1000)
    
    def get_openai_temperature(self) -> float:
        """Получает temperature для OpenAI."""
        return self.config.getfloat('openai', 'temperature', fallback=0.7)
    
    # Web App URLs
    def get_main_url(self) -> str:
        """Получает основной URL веб-приложения."""
        return self.config.get('web_app', 'main_url', fallback='')
    
    def get_spa_menu_url(self) -> str:
        """Получает URL SPA меню."""
        return self.config.get('web_app', 'spa_menu_url', fallback='')
    
    # Network Configuration
    def get_connection_timeout(self) -> float:
        """Получает таймаут подключения."""
        return self.config.getfloat('network', 'connection_timeout', fallback=10.0)
    
    def get_read_timeout(self) -> float:
        """Получает таймаут чтения."""
        return self.config.getfloat('network', 'read_timeout', fallback=30.0)
    
    def get_max_retry_attempts(self) -> int:
        """Получает максимальное количество попыток повтора."""
        return self.config.getint('network', 'max_retry_attempts', fallback=5)
    
    def get_retry_min_wait(self) -> float:
        """Получает минимальное время ожидания между попытками."""
        return self.config.getfloat('network', 'retry_min_wait', fallback=2.0)
    
    def get_retry_max_wait(self) -> float:
        """Получает максимальное время ожидания между попытками."""
        return self.config.getfloat('network', 'retry_max_wait', fallback=60.0)
    
    def get_retry_multiplier(self) -> float:
        """Получает множитель для экспоненциального ожидания."""
        return self.config.getfloat('network', 'retry_multiplier', fallback=2.0)
    
    def validate_config(self) -> Tuple[bool, List[str]]:
        """
        Валидирует конфигурацию на корректность.
        
        Returns:
            Tuple[bool, List[str]]: (is_valid, error_messages)
        """
        errors = []
        
        # Проверяем обязательные параметры
        required_params = {
            ('telegram', 'token'): "Токен Telegram бота не задан",
            ('google_sheets', 'credentials_path'): "Путь к credentials.json не задан",
        }
        
        for (section, option), error_msg in required_params.items():
            try:
                value = self.config.get(section, option)
                if not value or value.startswith('${'):
                    errors.append(error_msg)
            except (configparser.NoSectionError, configparser.NoOptionError):
                errors.append(error_msg)
        
        # Проверяем существование файлов
        credentials_path = self.get_credentials_path()
        if credentials_path and not os.path.exists(credentials_path):
            errors.append(f"Файл credentials.json не найден: {credentials_path}")
        
        # Проверяем числовые значения
        if self.get_monitoring_interval() <= 0:
            errors.append("Интервал мониторинга должен быть больше 0")
        
        if self.get_max_retries() < 1:
            errors.append("Максимальное количество попыток должно быть больше 0")
        
        return len(errors) == 0, errors
    
    def get_config_summary(self) -> Dict[str, Any]:
        """
        Возвращает сводку текущей конфигурации для логирования.
        
        Returns:
            Dict[str, Any]: Словарь с настройками (без секретных данных)
        """
        return {
            'debug_mode': self.is_debug_mode(),
            'monitoring_interval': self.get_monitoring_interval(),
            'cache_cleanup_interval': self.get_cache_cleanup_interval(),
            'max_retries': self.get_max_retries(),
            'auth_max_attempts': self.get_auth_max_attempts(),
            'cache_ttl': self.get_cache_ttl(),
            'promotions_monitoring_interval': self.get_promotions_monitoring_interval(),
            'has_credentials': bool(os.path.exists(self.get_credentials_path())),
            'has_telegram_token': bool(self.get_telegram_token() and not self.get_telegram_token().startswith('${')),
            'has_openai_key': bool(self.get_openai_api_key() and not self.get_openai_api_key().startswith('${')),
        }

# Глобальный экземпляр менеджера конфигурации
config_manager = ConfigManager()

# Функции совместимости с существующим кодом
def get_monitoring_interval() -> float:
    """Получает интервал мониторинга (совместимость)."""
    return config_manager.get_monitoring_interval()

def get_cache_cleanup_interval() -> float:
    """Получает интервал очистки кэша (совместимость)."""
    return config_manager.get_cache_cleanup_interval()

def validate_production_config() -> Tuple[bool, List[str]]:
    """Валидирует конфигурацию для production (совместимость)."""
    return config_manager.validate_config()