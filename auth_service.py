import logging
import datetime
from typing import Optional
import os

from cachetools import TTLCache
from sheets_gateway import AsyncGoogleSheetsGateway, CircuitBreakerOpenError
from sheets_gateway import _get_client_and_sheet, normalize_phone
from utils import mask_phone, mask_telegram_id

logger = logging.getLogger(__name__)





class AuthService:
    def __init__(self, gateway: Optional[AsyncGoogleSheetsGateway] = None):
        """Инициализация сервиса авторизации."""
        self.worksheet = None
        self.gateway = gateway or AsyncGoogleSheetsGateway(circuit_breaker_name='auth')
        self.auth_cache = TTLCache(maxsize=2000, ttl=300)
        
        # Синхронная инициализация для обратной совместимости
        try:
            _, worksheet = _get_client_and_sheet()
            self.worksheet = worksheet
            logger.info("Worksheet успешно инициализирован через sheets_gateway")
        except Exception as e:
            logger.error(f"Не удалось инициализировать worksheet: {e}")

    async def initialize(self):
        """Асинхронная инициализация доступа к Google Sheets."""
        try:
            client = await self.gateway.authorize_client()
            sheet_id = os.environ.get('SHEET_ID')
            if not sheet_id:
                logger.error("SHEET_ID не задан")
                return
            spreadsheet = await self.gateway.open_spreadsheet(client, sheet_id)
            sheet_name = os.environ.get('SHEET_NAME', 'Sheet1')
            self.worksheet = await self.gateway.get_worksheet_async(spreadsheet, sheet_name)
            logger.info(f"AuthService успешно инициализирован асинхронно: {sheet_name}")
        except Exception as e:
            logger.error(f"Ошибка асинхронной инициализации AuthService: {e}")

    async def find_and_update_user(self, partner_code: str, partner_phone: str, telegram_id: int) -> bool:
        """
        Ищет пользователя и обновляет его статус авторизации.
        
        Args:
            partner_code: код партнера
            partner_phone: телефон партнера
            telegram_id: ID пользователя в Telegram
            
        Returns:
            bool: True если пользователь найден и авторизован
        """
        logger.info(f"Поиск пользователя: код={partner_code}, телефон={mask_phone(partner_phone)}, telegram_id={mask_telegram_id(telegram_id)}")

        if not self.worksheet:
            logger.error("Worksheet не инициализирован (Sheets конфигурация отсутствует).")
            return False

        try:
            if not partner_code or not partner_phone:
                logger.warning("Получены пустые данные для поиска пользователя")
                return False

            phone_norm = normalize_phone(partner_phone)
            logger.info(f"Нормализованный телефон из формы: '{mask_phone(phone_norm)}'")
            
            # Получаем все записи через Gateway
            records = await self.gateway.get_all_records(self.worksheet)
            logger.info(f"Получено {len(records)} записей для поиска пользователя")
            
            row_index: Optional[int] = None
            for i, record in enumerate(records, start=2):  # start=2 потому что строка 1 - заголовки
                code_in_row = str(record.get('partner_code', record.get('Код партнера', ''))).strip()
                phone_in_row = str(record.get('phone', record.get('Телефон партнера', ''))).strip()
                normalized_row_phone = normalize_phone(phone_in_row)
                
                if code_in_row == partner_code and normalized_row_phone == phone_norm:
                    row_index = i
                    logger.info(f"Найдена строка с пользователем: {row_index}")
                    break

            if row_index:
                # Обновляем статус/telegram_id через Gateway
                try:
                    timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    # Обновляем статус (D), telegram_id (E), дату (F)
                    await self.gateway.update(self.worksheet, f'D{row_index}:F{row_index}', [[
                        'authorized',
                        str(telegram_id),
                        timestamp
                    ]])
                    logger.info(f"Пользователь с кодом {partner_code} успешно авторизован.")
                    
                    # Обновляем кэш
                    self.auth_cache[telegram_id] = True
                    return True
                except CircuitBreakerOpenError as e:
                    logger.warning(f"Circuit Breaker открыт для Auth Service: {e}")
                    return False
                except Exception as e:
                    logger.error(f"Ошибка обновления строки {row_index}: {e}")
                    return False

            logger.warning(
                f"Пользователь с кодом {partner_code} и телефоном {partner_phone} не найден."
            )
            return False
        except CircuitBreakerOpenError as e:
            logger.warning(f"Circuit Breaker открыт для Auth Service: {e}")
            return False
        except Exception as e:
            logger.error(f"Ошибка при поиске и обновлении пользователя: {e}")
            return False

    async def get_user_auth_status(self, telegram_id: int) -> bool:
        """
        Проверяет статус авторизации пользователя по Telegram ID.
        Использует TTLCache для оптимизации.
        
        Args:
            telegram_id: ID пользователя в Telegram
            
        Returns:
            bool: True если пользователь авторизован
        """
        logger.info(f"Проверка статуса авторизации для пользователя {mask_telegram_id(telegram_id)}")
        
        # Проверяем кэш сначала
        if telegram_id in self.auth_cache:
            logger.info(f"Используем кэшированный результат для пользователя {mask_telegram_id(telegram_id)}")
            return self.auth_cache[telegram_id]
        
        # Если не в кэше, проверяем в таблице
        if not self.worksheet:
            logger.error("Worksheet не инициализирован.")
            return False

        try:
            logger.info("Получение всех записей из таблицы для проверки статуса...")
            records = await self.gateway.get_all_records(self.worksheet)
            logger.info(f"Получено {len(records)} записей из таблицы для проверки статуса")
            
            for i, row in enumerate(records):
                logger.info(f"Проверка записи {i+1} для статуса: {row}")
                
                # Проверяем, есть ли 'Telegram ID' в строке и совпадает ли он
                telegram_id_in_sheet = row.get('Telegram ID')
                logger.info(f"Сравнение Telegram ID: в таблице='{mask_telegram_id(telegram_id_in_sheet)}' vs запрашиваемый='{mask_telegram_id(telegram_id)}'")
                
                if str(telegram_id_in_sheet) == str(telegram_id):
                    # Проверяем статус в колонке 'Статус' или 'Статус авторизации'
                    status = row.get('Статус') or row.get('Статус авторизации')
                    logger.info(f"Найден пользователь с Telegram ID {mask_telegram_id(telegram_id)}, статус: {status}")
                    status_norm = str(status or '').strip().lower()
                    result = status_norm in ("авторизован", "authorized")
                    logger.info(f"Результат проверки авторизации: {result}")
                    
                    # Обновляем кэш
                    self.auth_cache[telegram_id] = result
                    return result
                else:
                    logger.info(f"Запись {i+1} не соответствует запрашиваемому Telegram ID")
                    
            logger.info(f"Пользователь с Telegram ID {mask_telegram_id(telegram_id)} не найден в таблице")
            # Обновляем кэш с результатом "не авторизован"
            self.auth_cache[telegram_id] = False
            return False
        except CircuitBreakerOpenError as e:
            logger.warning(f"Circuit Breaker открыт для Auth Service: {e}. Возвращаем False.")
            return False
        except Exception as e:
            logger.error(f"Ошибка при проверке статуса пользователя {mask_telegram_id(telegram_id)}: {e}", exc_info=True)
            # При ошибке возвращаем False (fail-safe)
            return False

    def force_check_auth_status(self, telegram_id: int) -> bool:
        """
        СИНХРОННАЯ заглушка. Для реальной проверки используйте `await get_user_auth_status`.
        """
        # Возвращаем текущее значение из кэша, если оно есть
        return self.auth_cache.get(telegram_id, False)

    def clear_auth_cache(self, telegram_id: int = None):
        """Очищает кэш авторизации для конкретного пользователя или всех пользователей."""
        if telegram_id:
            if telegram_id in self.auth_cache:
                del self.auth_cache[telegram_id]
                logger.info(f"Кэш авторизации очищен для пользователя {mask_telegram_id(telegram_id)}")
        else:
            self.auth_cache.clear()
            logger.info("Кэш авторизации очищен для всех пользователей")
