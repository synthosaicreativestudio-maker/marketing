"""Сервис уведомлений о новых акциях"""
import logging
import asyncio
from typing import List, Dict

from promotions_api import check_new_promotions, is_promotions_available
from auth_service import AuthService

logger = logging.getLogger(__name__)

class PromotionsNotifier:
    """Сервис для отправки уведомлений о новых акциях"""
    
    def __init__(self, bot, auth_service: AuthService):
        self.bot = bot
        self.auth_service = auth_service
        self.last_check_time = None
        self.sent_promotions = set()  # Множество ID уже отправленных акций
        
    async def check_and_send_notifications(self):
        """Проверяет новые акции и отправляет уведомления"""
        if not is_promotions_available():
            logger.warning("Система акций недоступна, пропускаем проверку уведомлений")
            return
            
        try:
            new_promotions = check_new_promotions()
            
            if not new_promotions:
                logger.info("Новых акций не найдено")
                return
                
            # Получаем список авторизованных пользователей
            authorized_users = await self._get_authorized_users()
            
            if not authorized_users:
                logger.info("Нет авторизованных пользователей для отправки уведомлений")
                return
                
            # Отправляем уведомления о новых акциях
            for promotion in new_promotions:
                if promotion['id'] not in self.sent_promotions:
                    await self._send_promotion_notification(promotion, authorized_users)
                    self.sent_promotions.add(promotion['id'])
                    
        except Exception as e:
            logger.error(f"Ошибка при проверке и отправке уведомлений о акциях: {e}")
    
    async def _get_authorized_users(self) -> List[int]:
        """Получает список ID авторизованных пользователей"""
        try:
            if not self.auth_service.worksheet:
                return []
                
            records = self.auth_service.worksheet.get_all_records()
            authorized_users = []
            
            for record in records:
                telegram_id = record.get('Telegram ID')
                status = record.get('Статус') or record.get('Статус авторизации')
                
                if telegram_id and str(status).strip().lower() in ('авторизован', 'authorized'):
                    try:
                        authorized_users.append(int(telegram_id))
                    except (ValueError, TypeError):
                        continue
                        
            logger.info(f"Найдено {len(authorized_users)} авторизованных пользователей")
            return authorized_users
            
        except Exception as e:
            logger.error(f"Ошибка при получении списка авторизованных пользователей: {e}")
            return []
    
    async def _send_promotion_notification(self, promotion: Dict, users: List[int]):
        """Отправляет уведомление о новой акции пользователям"""
        try:
            # Формируем сообщение
            message = "🎉 **Новая акция!**\n\n"
            message += f"**{promotion['title']}**\n\n"
            message += f"📝 {promotion['description'][:200]}{'...' if len(promotion['description']) > 200 else ''}\n\n"
            message += f"📅 **Период действия:** {promotion['start_date']} - {promotion['end_date']}\n\n"
            message += f"✨ Акция активна с {promotion['release_date']}"
            
            # Создаем инлайн кнопку
            from telegram import InlineKeyboardButton, InlineKeyboardMarkup
            keyboard = [[
                InlineKeyboardButton(
                    "📋 Посмотреть все акции", 
                    web_app={"url": "https://synthosaicreativestudio-maker.github.io/marketing/menu.html"}
                )
            ]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            # Отправляем уведомления всем пользователям
            sent_count = 0
            for user_id in users:
                try:
                    await self.bot.send_message(
                        chat_id=user_id,
                        text=message,
                        parse_mode='Markdown',
                        reply_markup=reply_markup
                    )
                    sent_count += 1
                    logger.info(f"Уведомление о акции '{promotion['title']}' отправлено пользователю {user_id}")
                    
                    # Небольшая задержка между отправками
                    await asyncio.sleep(0.1)
                    
                except Exception as e:
                    logger.warning(f"Не удалось отправить уведомление пользователю {user_id}: {e}")
                    continue
            
            logger.info(f"Уведомление о акции '{promotion['title']}' отправлено {sent_count} пользователям")
            
        except Exception as e:
            logger.error(f"Ошибка при отправке уведомления о акции: {e}")
    
    async def start_monitoring(self, interval_minutes: int = 15):
        """Запускает мониторинг новых акций"""
        logger.info(f"Запуск мониторинга акций (проверка каждые {interval_minutes} минут)")
        
        while True:
            try:
                await self.check_and_send_notifications()
                await asyncio.sleep(interval_minutes * 60)
            except Exception as e:
                logger.error(f"Ошибка в мониторинге акций: {e}")
                await asyncio.sleep(60)  # Ждем минуту при ошибке
