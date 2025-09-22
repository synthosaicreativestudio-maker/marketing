import logging
import datetime
from typing import Optional

from sheets import (
    _get_client_and_sheet,
    find_row_by_partner_and_phone,
    update_row_with_auth,
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
        try:
            _, worksheet = _get_client_and_sheet()
            self.worksheet = worksheet
            logger.info("Worksheet успешно инициализирован через sheets.py")
        except SheetsNotConfiguredError as e:
            logger.critical(f"Sheets не сконфигурирован: {e}")
        except Exception as e:
            logger.critical(f"Не удалось инициализировать доступ к Google Sheets: {e}")

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
        """
        logger.info(f"Проверка статуса авторизации для пользователя {telegram_id}")
        
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
                    # Проверяем статус в колонке 'Статус'
                    status = row.get('Статус')
                    logger.info(f"Найден пользователь с Telegram ID {telegram_id}, статус: {status}")
                    result = status in ("Авторизован", "authorized")
                    logger.info(f"Результат проверки авторизации: {result}")
                    return result
                else:
                    logger.info(f"Запись {i+1} не соответствует запрашиваемому Telegram ID")
                    
            logger.info(f"Пользователь с Telegram ID {telegram_id} не найден в таблице")
            return False
        except Exception as e:
            logger.error(f"Ошибка при проверке статуса пользователя: {e}")
            return False
