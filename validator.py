"""
Модуль для валидации данных
Централизованная проверка входных данных и параметров
"""

import re
import logging
from typing import Optional, Tuple, Dict, Any

logger = logging.getLogger(__name__)

class DataValidator:
    """Класс для валидации различных типов данных"""
    
    @staticmethod
    def validate_phone(phone: str) -> Tuple[bool, str]:
        """Валидирует номер телефона"""
        if not phone or not isinstance(phone, str):
            return False, "Номер телефона не указан"
        
        # Очищаем от всех символов кроме цифр
        clean_phone = re.sub(r'\D', '', phone)
        
        if len(clean_phone) < 10:
            return False, "Номер телефона слишком короткий"
        
        if len(clean_phone) > 12:
            return False, "Номер телефона слишком длинный"
        
        # Проверяем российские номера
        if clean_phone.startswith('8') and len(clean_phone) == 11:
            return True, clean_phone
        elif clean_phone.startswith('7') and len(clean_phone) == 11:
            return True, clean_phone
        elif len(clean_phone) == 10:
            return True, f"7{clean_phone}"
        
        return True, clean_phone
    
    @staticmethod
    def validate_partner_code(code: str) -> Tuple[bool, str]:
        """Валидирует код партнера"""
        if not code or not isinstance(code, str):
            return False, "Код партнера не указан"
        
        code = code.strip()
        
        if len(code) < 3:
            return False, "Код партнера слишком короткий (минимум 3 символа)"
        
        if len(code) > 20:
            return False, "Код партнера слишком длинный (максимум 20 символов)"
        
        # Проверяем на допустимые символы (буквы, цифры, дефис, подчеркивание)
        if not re.match(r'^[a-zA-Z0-9_-]+$', code):
            return False, "Код партнера содержит недопустимые символы"
        
        return True, code
    
    @staticmethod
    def validate_telegram_id(telegram_id: Any) -> Tuple[bool, int]:
        """Валидирует Telegram ID"""
        try:
            tid = int(telegram_id)
            if tid <= 0:
                return False, 0
            return True, tid
        except (ValueError, TypeError):
            return False, 0
    
    @staticmethod
    def validate_menu_selection(payload: Dict[str, Any]) -> Tuple[bool, str]:
        """Валидирует данные выбора меню"""
        section = payload.get('section')
        
        if not section or not isinstance(section, str):
            return False, "Не указан раздел меню"
        
        from config import SECTIONS
        if section not in SECTIONS:
            return False, f"Неизвестный раздел: {section}"
        
        return True, ""
    
    @staticmethod
    def validate_subsection_selection(payload: Dict[str, Any]) -> Tuple[bool, str]:
        """Валидирует данные выбора подраздела"""
        section = payload.get('section')
        subsection = payload.get('subsection')
        
        if not section or not isinstance(section, str):
            return False, "Не указан раздел"
        
        if not subsection or not isinstance(subsection, str):
            return False, "Не указан подраздел"
        
        from config import SUBSECTIONS
        if section not in SUBSECTIONS:
            return False, f"Неизвестный раздел: {section}"
        
        if subsection not in SUBSECTIONS[section]:
            return False, f"Неизвестный подраздел {subsection} в разделе {section}"
        
        return True, ""
    
    @staticmethod
    def validate_web_app_data(raw_data: str) -> Tuple[bool, Optional[Dict], str]:
        """Валидирует данные от веб-приложения"""
        try:
            import json
            payload = json.loads(raw_data)
            
            if not isinstance(payload, dict):
                return False, None, "Данные должны быть объектом JSON"
            
            return True, payload, ""
            
        except json.JSONDecodeError as e:
            return False, None, f"Некорректный JSON: {str(e)}"
        except Exception as e:
            return False, None, f"Ошибка обработки данных: {str(e)}"
    
    @staticmethod
    def sanitize_text(text: str, max_length: int = 1000) -> str:
        """Очищает и обрезает текст"""
        if not text or not isinstance(text, str):
            return ""
        
        # Удаляем потенциально опасные символы
        sanitized = re.sub(r'[<>\"\'&]', '', text)
        
        # Обрезаем до максимальной длины
        if len(sanitized) > max_length:
            sanitized = sanitized[:max_length] + "..."
        
        return sanitized.strip()
    
    @staticmethod
    def validate_environment() -> Tuple[bool, list]:
        """Валидирует переменные окружения"""
        import os
        errors = []
        
        required_vars = {
            'TELEGRAM_TOKEN': 'Токен Telegram бота',
            'SHEET_URL': 'URL таблицы авторизации',
            'TICKETS_SHEET_URL': 'URL таблицы обращений'
        }
        
        for var, description in required_vars.items():
            value = os.getenv(var)
            if not value:
                errors.append(f"Отсутствует {description} ({var})")
            elif var == 'TELEGRAM_TOKEN':
                # More strict validation for Telegram token
                if not (len(value) > 40 and ':' in value and value.count(':') == 1):
                    errors.append("Некорректный формат токена бота")
                # Check for potential exposed token
                if value.startswith('"') and value.endswith('"'):
                    logger.warning(f'{var} contains quotes - this may indicate exposed credentials')
            elif 'SHEET_URL' in var:
                if 'docs.google.com/spreadsheets' not in value:
                    errors.append(f"Некорректный URL Google Sheets для {description}")
                elif not value.startswith('https://'):
                    errors.append(f"Небезопасный URL (HTTP вместо HTTPS) для {description}")
        
        # Additional security checks
        admin_id = os.getenv('ADMIN_TELEGRAM_ID', '')
        if admin_id:
            admin_ids = [s.strip() for s in admin_id.split(',') if s.strip()]
            invalid_ids = [aid for aid in admin_ids if not aid.isdigit()]
            if invalid_ids:
                errors.append(f"Некорректные admin ID: {invalid_ids}")
        
        openai_key = os.getenv('OPENAI_API_KEY', '')
        if openai_key and not openai_key.startswith('sk-'):
            errors.append("Некорректный формат OpenAI API key")
        
        return len(errors) == 0, errors

# Экземпляр валидатора
validator = DataValidator()