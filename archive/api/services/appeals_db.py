"""
Сервис для работы с обращениями через базу данных.
Замена для AppealsService (Google Sheets).
Идентичный интерфейс для совместимости с существующим кодом.
"""
import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict
from sqlalchemy.orm import Session
from db.models import Appeal, AppealMessage, SpecialistResponse

logger = logging.getLogger(__name__)


class AppealsServiceDB:
    """
    Сервис для работы с обращениями в базе данных.
    Полный аналог AppealsService, но работает с БД вместо Google Sheets.
    """
    
    def __init__(self, db: Session):
        """
        Инициализация сервиса.
        
        Args:
            db: SQLAlchemy сессия базы данных
        """
        self.db = db
    
    def is_available(self) -> bool:
        """Проверяет доступность сервиса обращений."""
        try:
            # Простая проверка подключения
            self.db.execute("SELECT 1")
            return True
        except Exception as e:
            logger.error(f"Сервис обращений недоступен: {e}")
            return False
    
    def create_appeal(self, code: str, phone: str, fio: str, telegram_id: int, text: str) -> bool:
        """
        Создает или обновляет обращение.
        
        Args:
            code: код партнера
            phone: телефон партнера
            fio: ФИО партнера
            telegram_id: ID пользователя в Telegram
            text: текст обращения
            
        Returns:
            bool: True если обращение создано/обновлено успешно
        """
        try:
            logger.info(f"Создание обращения для telegram_id={telegram_id}, code={code}, phone={phone}, fio={fio}")
            
            # Ищем существующее обращение
            appeal = self.db.query(Appeal).filter(
                Appeal.telegram_id == telegram_id
            ).first()
            
            if appeal:
                # Обновляем существующее обращение
                logger.info(f"Найдено существующее обращение {appeal.id} для telegram_id {telegram_id}")
                appeal.partner_code = code or appeal.partner_code
                appeal.phone = phone or appeal.phone
                appeal.fio = fio or appeal.fio
                appeal.updated_at = datetime.utcnow()
            else:
                # Создаем новое обращение
                logger.info(f"Создание нового обращения для telegram_id {telegram_id}")
                appeal = Appeal(
                    telegram_id=telegram_id,
                    partner_code=code,
                    phone=phone,
                    fio=fio,
                    status='новое'
                )
                self.db.add(appeal)
                self.db.flush()  # Получаем ID
            
            # Добавляем сообщение пользователя
            message = AppealMessage(
                appeal_id=appeal.id,
                message_type='user',
                message_text=text
            )
            self.db.add(message)
            
            # Очищаем старые сообщения (>30 дней)
            self._cleanup_old_messages(appeal.id)
            
            self.db.commit()
            logger.info(f"Обращение создано/обновлено для пользователя {telegram_id} (ID: {appeal.id})")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка создания/обновления обращения: {e}", exc_info=True)
            self.db.rollback()
            return False
    
    def _cleanup_old_messages(self, appeal_id: int):
        """Очищает сообщения старше 30 дней."""
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=30)
            old_messages = self.db.query(AppealMessage).filter(
                AppealMessage.appeal_id == appeal_id,
                AppealMessage.created_at < cutoff_date
            ).all()
            
            for msg in old_messages:
                self.db.delete(msg)
            
            if old_messages:
                logger.info(f"Удалено {len(old_messages)} старых сообщений для обращения {appeal_id}")
        except Exception as e:
            logger.error(f"Ошибка очистки старых сообщений: {e}")
    
    def get_appeal_status(self, telegram_id: int) -> str:
        """
        Получает статус обращения пользователя.
        
        Args:
            telegram_id: ID пользователя в Telegram
            
        Returns:
            str: статус обращения или 'новое' если не найден
        """
        try:
            appeal = self.db.query(Appeal).filter(
                Appeal.telegram_id == telegram_id
            ).first()
            
            if appeal:
                status = appeal.status
                logger.info(f"Найден статус для пользователя {telegram_id}: {status}")
                return status
            else:
                logger.info(f"Статус для пользователя {telegram_id} не найден, возвращаем 'новое'")
                return 'новое'
                
        except Exception as e:
            logger.error(f"Ошибка получения статуса обращения: {e}")
            return 'новое'
    
    def set_status_in_work(self, telegram_id: int) -> bool:
        """
        Устанавливает статус обращения на 'В работе'.
        
        Args:
            telegram_id: ID пользователя в Telegram
            
        Returns:
            bool: True если статус установлен успешно
        """
        try:
            appeal = self.db.query(Appeal).filter(
                Appeal.telegram_id == telegram_id
            ).first()
            
            if appeal:
                appeal.status = 'в_работе'
                appeal.updated_at = datetime.utcnow()
                self.db.commit()
                logger.info(f"Статус установлен 'В работе' для пользователя {telegram_id} (ID: {appeal.id})")
                return True
            else:
                logger.warning(f"Не найдена строка для пользователя {telegram_id}")
                return False
                
        except Exception as e:
            logger.error(f"Ошибка при установке статуса 'В работе': {e}")
            self.db.rollback()
            return False
    
    def set_status_escalated(self, telegram_id: int) -> bool:
        """
        Устанавливает статус обращения на 'Передано специалисту'.
        
        Args:
            telegram_id: ID пользователя в Telegram
            
        Returns:
            bool: True если статус установлен успешно
        """
        try:
            appeal = self.db.query(Appeal).filter(
                Appeal.telegram_id == telegram_id
            ).first()
            
            if appeal:
                appeal.status = 'передано_специалисту'
                appeal.updated_at = datetime.utcnow()
                self.db.commit()
                logger.info(f"Статус установлен 'Передано специалисту' для пользователя {telegram_id} (ID: {appeal.id})")
                return True
            else:
                logger.warning(f"Не найдена строка для пользователя {telegram_id}")
                return False
                
        except Exception as e:
            logger.error(f"Ошибка установки статуса 'Передано специалисту': {e}")
            self.db.rollback()
            return False
    
    def set_status_resolved(self, telegram_id: int) -> bool:
        """
        Устанавливает статус обращения на 'Решено'.
        
        Args:
            telegram_id: ID пользователя в Telegram
            
        Returns:
            bool: True если статус установлен успешно
        """
        try:
            appeal = self.db.query(Appeal).filter(
                Appeal.telegram_id == telegram_id
            ).first()
            
            if appeal:
                appeal.status = 'решено'
                appeal.updated_at = datetime.utcnow()
                self.db.commit()
                logger.info(f"Статус установлен 'Решено' для пользователя {telegram_id} (ID: {appeal.id})")
                return True
            else:
                logger.warning(f"Не найдена строка для пользователя {telegram_id}")
                return False
                
        except Exception as e:
            logger.error(f"Ошибка при установке статуса 'Решено': {e}")
            self.db.rollback()
            return False
    
    def add_ai_response(self, telegram_id: int, response_text: str) -> bool:
        """
        Добавляет ответ ИИ к существующим обращениям пользователя.
        
        Args:
            telegram_id: ID пользователя в Telegram
            response_text: текст ответа ИИ
            
        Returns:
            bool: True если ответ добавлен успешно
        """
        try:
            appeal = self.db.query(Appeal).filter(
                Appeal.telegram_id == telegram_id
            ).first()
            
            if appeal:
                # Добавляем сообщение от ИИ
                message = AppealMessage(
                    appeal_id=appeal.id,
                    message_type='ai',
                    message_text=response_text
                )
                self.db.add(message)
                
                # Обновляем статус
                appeal.status = 'ответ_ии'
                appeal.updated_at = datetime.utcnow()
                
                self.db.commit()
                logger.info(f"Ответ ИИ добавлен для пользователя {telegram_id} (ID: {appeal.id})")
                return True
            else:
                logger.warning(f"Не найдена строка для пользователя {telegram_id}")
                return False
                
        except Exception as e:
            logger.error(f"Ошибка добавления ответа ИИ: {e}")
            self.db.rollback()
            return False
    
    def add_user_message(self, telegram_id: int, message_text: str) -> bool:
        """
        Гарантированно добавляет пользовательское сообщение без изменения статуса.
        Используется как дополнительная страховка при режиме специалиста.
        
        Args:
            telegram_id: ID пользователя в Telegram
            message_text: текст сообщения
            
        Returns:
            bool: True если сообщение добавлено успешно
        """
        try:
            appeal = self.db.query(Appeal).filter(
                Appeal.telegram_id == telegram_id
            ).first()
            
            if appeal:
                message = AppealMessage(
                    appeal_id=appeal.id,
                    message_type='user',
                    message_text=message_text
                )
                self.db.add(message)
                appeal.updated_at = datetime.utcnow()
                self.db.commit()
                logger.info(f"Сообщение пользователя добавлено для {telegram_id} (ID: {appeal.id})")
                return True
            else:
                logger.warning(f"Строка пользователя не найдена для добавления сообщения (telegram_id={telegram_id})")
                return False
                
        except Exception as e:
            logger.error(f"Ошибка добавления пользовательского сообщения: {e}")
            self.db.rollback()
            return False
    
    def add_specialist_response(self, telegram_id: int, response_text: str) -> bool:
        """
        Добавляет ответ специалиста к существующим обращениям пользователя.
        
        Args:
            telegram_id: ID пользователя в Telegram
            response_text: текст ответа специалиста
            
        Returns:
            bool: True если ответ добавлен успешно
        """
        try:
            appeal = self.db.query(Appeal).filter(
                Appeal.telegram_id == telegram_id
            ).first()
            
            if appeal:
                # Добавляем сообщение от специалиста
                message = AppealMessage(
                    appeal_id=appeal.id,
                    message_type='specialist',
                    message_text=f"👨‍💼 СПЕЦИАЛИСТ: {response_text}"
                )
                self.db.add(message)
                
                # Создаем запись ответа специалиста
                specialist_response = SpecialistResponse(
                    appeal_id=appeal.id,
                    response_text=response_text
                )
                self.db.add(specialist_response)
                
                appeal.updated_at = datetime.utcnow()
                self.db.commit()
                logger.info(f"Ответ специалиста добавлен для пользователя {telegram_id} (ID: {appeal.id})")
                return True
            else:
                logger.warning(f"Не найдена строка для пользователя {telegram_id}")
                return False
                
        except Exception as e:
            logger.error(f"Ошибка добавления ответа специалиста: {e}")
            self.db.rollback()
            return False
    
    def check_for_responses(self) -> List[Dict]:
        """
        Проверяет наличие новых ответов специалистов для отправки.
        В БД ответы отправляются через API, но этот метод оставлен для совместимости
        с ResponseMonitor (который может проверять БД периодически).
        
        Returns:
            List[Dict]: список ответов для отправки
        """
        try:
            # Ищем ответы специалистов, которые еще не были отправлены
            # В новой архитектуре это можно отслеживать через флаг sent_to_user
            # Пока возвращаем пустой список, так как отправка через API
            # Если нужно, можно добавить поле is_sent в SpecialistResponse
            return []
        except Exception as e:
            logger.error(f"Ошибка проверки ответов: {e}")
            return []
    
    def clear_response(self, row: int) -> bool:
        """
        Очищает ответ специалиста.
        В БД это не нужно, так как ответы хранятся в отдельной таблице.
        Оставлено для совместимости.
        
        Args:
            row: номер строки (не используется в БД)
            
        Returns:
            bool: True
        """
        # В БД ответы не нужно очищать, они хранятся в истории
        return True
    
    def has_records(self) -> bool:
        """
        Проверяет, есть ли записи в таблице.
        
        Returns:
            bool: True если есть записи
        """
        try:
            count = self.db.query(Appeal).count()
            return count > 0
        except Exception as e:
            logger.error(f"Ошибка проверки наличия записей: {e}")
            return False
    
    def get_user_appeals(self, telegram_id: int) -> List[Dict]:
        """
        Получает все обращения пользователя.
        
        Args:
            telegram_id: ID пользователя в Telegram
            
        Returns:
            List[Dict]: список обращений пользователя
        """
        try:
            appeals = self.db.query(Appeal).filter(
                Appeal.telegram_id == telegram_id
            ).all()
            
            result = []
            for appeal in appeals:
                result.append({
                    'id': appeal.id,
                    'telegram_id': appeal.telegram_id,
                    'partner_code': appeal.partner_code,
                    'phone': appeal.phone,
                    'fio': appeal.fio,
                    'status': appeal.status,
                    'created_at': appeal.created_at.isoformat() if appeal.created_at else None,
                    'updated_at': appeal.updated_at.isoformat() if appeal.updated_at else None
                })
            
            logger.info(f"Найдено {len(result)} обращений для пользователя {telegram_id}")
            return result
            
        except Exception as e:
            logger.error(f"Ошибка получения обращений пользователя: {e}")
            return []
    
    def get_all_appeals(self, status: Optional[str] = None) -> List[Dict]:
        """
        Получает все обращения, опционально фильтруя по статусу.
        
        Args:
            status: статус для фильтрации (опционально)
            
        Returns:
            List[Dict]: список всех обращений
        """
        try:
            query = self.db.query(Appeal)
            
            if status:
                query = query.filter(Appeal.status == status)
            
            appeals = query.all()
            
            result = []
            for appeal in appeals:
                result.append({
                    'id': appeal.id,
                    'telegram_id': appeal.telegram_id,
                    'partner_code': appeal.partner_code,
                    'phone': appeal.phone,
                    'fio': appeal.fio,
                    'status': appeal.status,
                    'created_at': appeal.created_at.isoformat() if appeal.created_at else None,
                    'updated_at': appeal.updated_at.isoformat() if appeal.updated_at else None
                })
            
            logger.info(f"Найдено {len(result)} обращений" + (f" со статусом '{status}'" if status else ""))
            return result
            
        except Exception as e:
            logger.error(f"Ошибка получения всех обращений: {e}")
            return []
    
    def check_for_resolved_status(self) -> List[Dict]:
        """
        Проверяет наличие обращений со статусом 'Решено', о которых еще не уведомлен пользователь.
        Оставлено для совместимости с ResponseMonitor.
        
        Returns:
            List[Dict]: список решенных обращений для уведомления
        """
        try:
            appeals = self.db.query(Appeal).filter(
                Appeal.status == 'решено'
            ).all()
            
            resolved_appeals = []
            for appeal in appeals:
                # Проверяем, есть ли маркер закрытия в последних сообщениях
                last_message = self.db.query(AppealMessage).filter(
                    AppealMessage.appeal_id == appeal.id
                ).order_by(AppealMessage.created_at.desc()).first()
                
                if last_message and "✅ Ваше обращение решено" not in last_message.message_text:
                    resolved_appeals.append({
                        'row': appeal.id,
                        'telegram_id': appeal.telegram_id,
                        'appeals_text': ''  # Не используется в БД
                    })
            
            if resolved_appeals:
                logger.info(f"Найдено {len(resolved_appeals)} решенных обращений для уведомления")
            
            return resolved_appeals
            
        except Exception as e:
            logger.error(f"Ошибка проверки решенных статусов: {e}")
            return []
