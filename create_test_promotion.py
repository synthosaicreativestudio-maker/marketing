#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Скрипт для создания тестовой акции в Google Sheets.
"""

import os
import sys
from dotenv import load_dotenv
from async_promotions_client import AsyncPromotionsClient
import asyncio
import logging
from datetime import date, timedelta

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def create_test_promotion():
    """
    Создает тестовую акцию в Google Sheets для тестирования уведомлений.
    """
    load_dotenv()
    
    # Получаем конфигурацию
    credentials_path = os.getenv('GOOGLE_CREDENTIALS_PATH', 'credentials.json')
    sheet_url = os.getenv('PROMOTIONS_SHEET_URL')
    
    if not sheet_url:
        logger.error("❌ PROMOTIONS_SHEET_URL не найден в .env файле")
        return False
    
    if not os.path.exists(credentials_path):
        logger.error(f"❌ Файл {credentials_path} не найден")
        return False
    
    try:
        # Создаем клиент
        client = AsyncPromotionsClient(credentials_path, sheet_url)
        
        # Подключаемся к таблице
        logger.info("🔗 Подключаемся к Google Sheets...")
        if not await client.connect():
            logger.error("❌ Не удалось подключиться к таблице")
            return False
        
        logger.info("✅ Подключение успешно!")
        
        # Получаем текущие данные
        all_values = await client._run_in_executor(client.sheet.get_all_values)
        
        # Находим первую пустую строку
        next_row = len(all_values) + 1
        
        # Создаем тестовую акцию
        today = date.today()
        start_date = today + timedelta(days=1)
        end_date = today + timedelta(days=30)
        
        test_promotion = [
            today.strftime('%d.%m.%Y'),  # Дата релиза
            'Тестовая акция для проверки уведомлений',  # Название
            'Это тестовая акция для проверки работы системы уведомлений бота',  # Описание
            'Опубликовано',  # Статус
            start_date.strftime('%d.%m.%Y'),  # Дата начала
            end_date.strftime('%d.%m.%Y'),  # Дата окончания
            'https://drive.google.com/file/d/1ABC123/view',  # Контент
            '',  # Кнопка
            ''  # Уведомление отправлено
        ]
        
        # Добавляем акцию в таблицу
        logger.info(f"📝 Добавляем тестовую акцию в строку {next_row}...")
        
        # Обновляем ячейки по одной
        for col_idx, value in enumerate(test_promotion, 1):
            await client._run_in_executor(
                client.sheet.update_cell, next_row, col_idx, value
            )
        
        logger.info("✅ Тестовая акция создана!")
        logger.info("📋 Детали акции:")
        logger.info(f"   Название: {test_promotion[1]}")
        logger.info(f"   Статус: {test_promotion[3]}")
        logger.info(f"   Период: {test_promotion[4]} - {test_promotion[5]}")
        logger.info(f"   Строка: {next_row}")
        
        logger.info("\n⏰ Ожидайте уведомление от бота через 30 секунд...")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Ошибка: {e}")
        return False

async def main():
    """
    Основная функция.
    """
    logger.info("🧪 Создание тестовой акции для проверки уведомлений...")
    
    success = await create_test_promotion()
    
    if success:
        logger.info("✅ Тестовая акция создана успешно!")
        sys.exit(0)
    else:
        logger.error("❌ Ошибка создания тестовой акции!")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())