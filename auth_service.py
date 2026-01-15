import logging
import datetime
from typing import Optional, Dict
import json
import os

from sheets_gateway import (
    _get_client_and_sheet,
    normalize_phone,
    SheetsNotConfiguredError,
)

logger = logging.getLogger(__name__)

class AuthService:
    def __init__(self):
        """Инициализация сервиса авторизации на основе sheets.py (вариант A).

        Используются переменные окружения:
        - SHEET_ID (обязательно)
        - SHEET_NAME (опционально, по умолчанию Sheet1)
        - GCP_SA_JSON или GCP_SA_FILE (обязательно один из)
        """
        self.worksheet = None
        self.auth_cache_file = "auth_cache.json"
        self.auth_cache = self._load_auth_cache()
        
        try:
            _, worksheet = _get_client_and_sheet()
            self.worksheet = worksheet
            logger.info("Worksheet успешно инициализирован через sheets.py")
        except SheetsNotConfiguredError as e:
            logger.critical(f"Sheets не сконфигурирован: {e}")
        except Exception as e:
            logger.critical(f"Не удалось инициализировать доступ к Google Sheets: {e}")

    def _load_auth_cache(self) -> Dict:
        """Загружает кэш авторизации из файла."""
        try:
            if os.path.exists(self.auth_cache_file):
                with open(self.auth_cache_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            logger.warning(f"Ошибка загрузки кэша авторизации: {e}")
        return {}

    def _save_auth_cache(self):
        """Сохраняет кэш авторизации в файл."""
        try:
            with open(self.auth_cache_file, 'w', encoding='utf-8') as f:
                json.dump(self.auth_cache, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"Ошибка сохранения кэша авторизации: {e}")

    def _is_auth_cache_valid(self, telegram_id: int, max_age_minutes: int = 5) -> bool:
        """Проверяет, действителен ли кэш авторизации для пользователя."""
        if str(telegram_id) not in self.auth_cache:
            return False
        
        cache_time = self.auth_cache[str(telegram_id)].get('timestamp')
        if not cache_time:
            return False
        
        try:
            cache_datetime = datetime.datetime.fromisoformat(cache_time)
            now = datetime.datetime.now()
            # Проверяем, прошло ли менее указанного количества минут
            return (now - cache_datetime).total_seconds() < max_age_minutes * 60
        except Exception as e:
            logger.warning(f"Ошибка проверки времени кэша: {e}")
            return False

    def _update_auth_cache(self, telegram_id: int, is_authorized: bool):
        """Обновляет кэш авторизации для пользователя."""
        self.auth_cache[str(telegram_id)] = {
            'is_authorized': is_authorized,
            'timestamp': datetime.datetime.now().isoformat()
        }
        self._save_auth_cache()
    
    def clear_auth_cache(self, telegram_id: int = None):
        """Очищает кэш авторизации для конкретного пользователя или всех пользователей."""
        if telegram_id:
            if str(telegram_id) in self.auth_cache:
                del self.auth_cache[str(telegram_id)]
                logger.info(f"Кэш авторизации очищен для пользователя {telegram_id}")
        else:
            self.auth_cache.clear()
            logger.info("Кэш авторизации очищен для всех пользователей")
        self._save_auth_cache()

    def find_and_update_user(self, partner_code: str, partner_phone: str, telegram_id: int) -> bool:
        """
        Ищет пользователя и обновляет его статус авторизации.
        """
        logger.info(f"Поиск пользователя: код={partner_code}, телефон={partner_phone}, telegram_id={telegram_id}")

        if not self.worksheet:
            logger.error("Worksheet не инициализирован (Sheets конфигурация отсутствует).")
            return False

        try:
            if not partner_code or not partner_phone:
                logger.warning("Получены пустые данные для поиска пользователя")
                return False

            phone_norm = normalize_phone(partner_phone)
            logger.info(f"Нормализованный телефон из формы: '{phone_norm}'")
            try:
                logger.info(f"Worksheet: '{self.worksheet.title}' — получаем записи...")
            except Exception:
                pass
            row_index: Optional[int] = find_row_by_partner_and_phone(partner_code, phone_norm)

            if row_index:
                logger.info(f"Найдена строка с пользователем: {row_index}")
                # Обновляем статус/telegram_id через batch API из sheets.py
                try:
                    update_row_with_auth(row_index, telegram_id, status='authorized')
                except Exception as e:
                    logger.error(f"Ошибка обновления строки {row_index}: {e}")
                    return False

                # Дополнительно обновим столбец с датой (F)
                try:
                    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    self.worksheet.update(f'F{row_index}', timestamp)
                except Exception as e:
                    logger.warning(f"Не удалось записать дату авторизации: {e}")

                logger.info(f"Пользователь с кодом {partner_code} успешно авторизован.")
                # Обновляем кэш авторизации
                self._update_auth_cache(telegram_id, True)
                return True

            logger.warning(
                f"Пользователь с кодом {partner_code} и телефоном {partner_phone} не найден."
            )
            return False
        except Exception as e:
            logger.error(f"Ошибка при поиске и обновлении пользователя: {e}")
            return False

    def get_user_auth_status(self, telegram_id: int) -> bool:
        """
        Проверяет статус авторизации пользователя по Telegram ID.
        Всегда проверяет актуальные данные в Google Sheets.
        """
        logger.info(f"Проверка статуса авторизации для пользователя {telegram_id}")
        
        # Проверяем кэш только для оптимизации (не более 5 минут)
        if self._is_auth_cache_valid(telegram_id, max_age_minutes=5):
            cached_result = self.auth_cache[str(telegram_id)]['is_authorized']
            logger.info(f"Используем кэшированный результат авторизации (актуальный): {cached_result}")
            return cached_result
        
        # Всегда проверяем актуальные данные в таблице
        if not self.worksheet:
            logger.error("Worksheet не инициализирован (Sheets конфигурация отсутствует).")
            return False

        try:
            logger.info("Получение всех записей из таблицы для проверки статуса...")
            records = self.worksheet.get_all_records()
            logger.info(f"Получено {len(records)} записей из таблицы для проверки статуса")
            
            for i, row in enumerate(records):
                logger.info(f"Проверка записи {i+1} для статуса: {row}")
                
                # Проверяем, есть ли 'Telegram ID' в строке и совпадает ли он
                telegram_id_in_sheet = row.get('Telegram ID')
                logger.info(f"Сравнение Telegram ID: в таблице='{telegram_id_in_sheet}' vs запрашиваемый='{telegram_id}'")
                
                if str(telegram_id_in_sheet) == str(telegram_id):
                    # Проверяем статус в колонке 'Статус' или 'Статус авторизации'
                    status = row.get('Статус') or row.get('Статус авторизации')
                    logger.info(f"Найден пользователь с Telegram ID {telegram_id}, статус: {status}")
                    status_norm = str(status or '').strip().lower()
                    result = status_norm in ("авторизован", "authorized")
                    logger.info(f"Результат проверки авторизации: {result}")
                    
                    # Обновляем кэш
                    self._update_auth_cache(telegram_id, result)
                    return result
                else:
                    logger.info(f"Запись {i+1} не соответствует запрашиваемому Telegram ID")
                    
            logger.info(f"Пользователь с Telegram ID {telegram_id} не найден в таблице")
            # Обновляем кэш с результатом "не авторизован"
            self._update_auth_cache(telegram_id, False)
            return False
        except Exception as e:
            logger.error(f"Ошибка при проверке статуса пользователя: {e}")
            # Инвалидируем кэш при ошибке
            self.clear_auth_cache(telegram_id)
            return False

    def force_check_auth_status(self, telegram_id: int) -> bool:
        """
        Принудительно проверяет статус авторизации пользователя, игнорируя кэш.
        Используется для обновления кэша при изменении статуса в таблице.
        """
        logger.info(f"Принудительная проверка статуса авторизации для пользователя {telegram_id}")
        
        if not self.worksheet:
            logger.error("Worksheet не инициализирован (Sheets конфигурация отсутствует).")
            return False

        try:
            logger.info("Получение всех записей из таблицы для принудительной проверки...")
            records = self.worksheet.get_all_records()
            logger.info(f"Получено {len(records)} записей из таблицы для принудительной проверки")
            
            for i, row in enumerate(records):
                # Проверяем, есть ли 'Telegram ID' в строке и совпадает ли он
                telegram_id_in_sheet = row.get('Telegram ID')
                
                if str(telegram_id_in_sheet) == str(telegram_id):
                    # Проверяем статус в колонке 'Статус' или 'Статус авторизации'
                    status = row.get('Статус') or row.get('Статус авторизации')
                    logger.info(f"Найден пользователь с Telegram ID {telegram_id}, статус: {status}")
                    status_norm = str(status or '').strip().lower()
                    result = status_norm in ("авторизован", "authorized")
                    logger.info(f"Результат принудительной проверки авторизации: {result}")
                    
                    # Обновляем кэш
                    self._update_auth_cache(telegram_id, result)
                    return result
                    
            logger.info(f"Пользователь с Telegram ID {telegram_id} не найден в таблице")
            # Обновляем кэш с результатом "не авторизован"
            self._update_auth_cache(telegram_id, False)
            return False
        except Exception as e:
            logger.error(f"Ошибка при принудительной проверке статуса пользователя: {e}")
            return False
