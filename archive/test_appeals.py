#!/usr/bin/env python3
"""
Тест для проверки записи обращений в таблицу.
"""

import logging
from dotenv import load_dotenv
from appeals_service import AppealsService

# Загружаем переменные окружения
load_dotenv()

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

def test_appeals():
    """Тестирует создание обращения."""
    logger.info("Запуск теста создания обращений...")
    
    # Инициализация сервиса обращений
    appeals_service = AppealsService()
    
    if not appeals_service.is_available():
        logger.error("AppealsService недоступен!")
        return False
    
    logger.info("AppealsService доступен")
    
    # Тестовые данные
    test_data = {
        'code': 'TEST001',
        'phone': '89199999999',
        'fio': 'Тестовый Пользователь',
        'telegram_id': 123456789,
        'text': 'Тестовое обращение для проверки записи в таблицу'
    }
    
    logger.info(f"Создание тестового обращения: {test_data}")
    
    # Создаем обращение
    result = appeals_service.create_appeal(
        code=test_data['code'],
        phone=test_data['phone'],
        fio=test_data['fio'],
        telegram_id=test_data['telegram_id'],
        text=test_data['text']
    )
    
    if result:
        logger.info("✅ Обращение успешно создано!")
        return True
    else:
        logger.error("❌ Ошибка создания обращения!")
        return False

if __name__ == "__main__":
    test_appeals()
