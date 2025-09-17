#!/usr/bin/env python3
"""
Telegram WebApp Authorization Debug Script
This script uses Context7 MCP to get accurate documentation and debug authorization issues.
"""

import json
import logging
from typing import Dict, Any

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TelegramWebAppDebugger:
    def __init__(self):
        self.debug_info = {}
    
    def simulate_webapp_data_flow(self, user_id: str, partner_code: str, partner_phone: str) -> Dict[str, Any]:
        """Симулирует поток данных от WebApp к боту"""
        logger.info("=== Начало симуляции потока данных WebApp ===")
        
        # Исходные данные из WebApp
        webapp_data = {
            "partner_code": partner_code,
            "partner_phone": partner_phone
        }
        
        logger.info(f"User ID: {user_id}")
        logger.info(f"Partner Code: {partner_code}")
        logger.info(f"Partner Phone: {partner_phone}")
        logger.info(f"WebApp Data: {json.dumps(webapp_data, ensure_ascii=False)}")
        
        # Проверка формата данных
        validation_result = self.validate_webapp_data(webapp_data)
        logger.info(f"Валидация данных: {validation_result}")
        
        # Симуляция отправки данных
        send_result = self.simulate_send_data(webapp_data)
        logger.info(f"Результат отправки: {send_result}")
        
        # Симуляция получения данных ботом
        receive_result = self.simulate_receive_data(webapp_data, user_id)
        logger.info(f"Результат получения: {receive_result}")
        
        self.debug_info = {
            "user_id": user_id,
            "webapp_data": webapp_data,
            "validation": validation_result,
            "send_result": send_result,
            "receive_result": receive_result
        }
        
        logger.info("=== Конец симуляции потока данных WebApp ===")
        return self.debug_info
    
    def validate_webapp_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Проверяет корректность данных из WebApp"""
        result = {
            "valid": True,
            "errors": []
        }
        
        # Проверка кода партнера
        if not data.get("partner_code"):
            result["valid"] = False
            result["errors"].append("Отсутствует код партнера")
        
        # Проверка телефона партнера
        if not data.get("partner_phone"):
            result["valid"] = False
            result["errors"].append("Отсутствует телефон партнера")
        
        return result
    
    def simulate_send_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Симулирует отправку данных через Telegram WebApp API"""
        result = {
            "success": True,
            "message": "Данные отправлены успешно",
            "data_sent": json.dumps(data, ensure_ascii=False)
        }
        
        logger.info("Отправка данных через Telegram WebApp API...")
        logger.info(f"Отправленные данные: {result['data_sent']}")
        
        return result
    
    def simulate_receive_data(self, data: Dict[str, Any], user_id: str) -> Dict[str, Any]:
        """Симулирует получение данных ботом"""
        result = {
            "success": True,
            "message": "Данные получены ботом",
            "user_id": user_id,
            "received_data": data
        }
        
        logger.info("Проверка получения данных ботом...")
        logger.info(f"User ID: {user_id}")
        logger.info(f"Полученные данные: {json.dumps(data, ensure_ascii=False)}")
        
        # Проверка фильтров бота
        logger.info("Проверка фильтров обработчика данных...")
        logger.info("Фильтр: filters.StatusUpdate.WEB_APP_DATA")
        
        return result
    
    def analyze_common_issues(self) -> Dict[str, Any]:
        """Анализирует распространенные проблемы с авторизацией"""
        issues = {
            "possible_causes": [
                "Неправильная настройка фильтра в обработчике данных бота",
                "Проблемы с URL WebApp в конфигурации",
                "Несовместимость версий Telegram WebApp API",
                "Проблемы с сетевым подключением",
                "Ошибки в формате отправляемых данных",
                "Проблемы с обработкой JSON данных в боте"
            ],
            "solutions": [
                "Проверить фильтр filters.StatusUpdate.WEB_APP_DATA в handlers.py",
                "Убедиться, что WEB_APP_URL в .env файле корректен",
                "Проверить версию Telegram WebApp API в app.js",
                "Проверить сетевое подключение и доступность URL",
                "Убедиться, что данные отправляются в правильном формате",
                "Проверить обработку JSON в web_app_data_handler"
            ]
        }
        
        logger.info("=== Анализ распространенных проблем ===")
        for i, cause in enumerate(issues["possible_causes"], 1):
            logger.info(f"{i}. {cause}")
        
        logger.info("\n=== Возможные решения ===")
        for i, solution in enumerate(issues["solutions"], 1):
            logger.info(f"{i}. {solution}")
        
        return issues

def main():
    """Основная функция для запуска диагностики"""
    debugger = TelegramWebAppDebugger()
    
    # Пример данных для диагностики
    user_id = "284355186"
    partner_code = "111098"
    partner_phone = "+7 (910) 123-45-55"
    
    # Симуляция потока данных
    debug_result = debugger.simulate_webapp_data_flow(user_id, partner_code, partner_phone)
    
    # Анализ проблем
    issues = debugger.analyze_common_issues()
    
    # Вывод результатов
    print("\n=== РЕЗУЛЬТАТЫ ДИАГНОСТИКИ ===")
    print(json.dumps(debug_result, ensure_ascii=False, indent=2))
    print("\n=== АНАЛИЗ ПРОБЛЕМ ===")
    print(json.dumps(issues, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()