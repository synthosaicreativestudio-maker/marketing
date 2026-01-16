"""Сервис уведомлений о новых акциях"""
import logging
import asyncio
from typing import List, Dict

from promotions_api import check_new_promotions, is_promotions_available
from auth_service import AuthService
from sheets_gateway import AsyncGoogleSheetsGateway

logger = logging.getLogger(__name__)

class PromotionsNotifier:
    """Сервис для отправки уведомлений о новых акциях"""
    
    def __init__(self, bot, auth_service: AuthService, gateway: AsyncGoogleSheetsGateway):
        self.bot = bot
        self.auth_service = auth_service
        self.gateway = gateway
        self.last_check_time = None
        self.sent_promotions = set()  # Множество ID уже отправленных акций
        self.is_running = False  # Флаг работы мониторинга
        self._task = None  # Ссылка на задачу мониторинга
        
    async def check_and_send_notifications(self):
        """Проверяет новые акции и отправляет уведомления"""
        if not await is_promotions_available(self.gateway):
            logger.warning("Система акций недоступна, пропускаем проверку уведомлений")
            return
            
        try:
            new_promotions = await check_new_promotions(self.gateway)
            
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
                
            records = await self.auth_service.gateway.get_all_records(self.auth_service.worksheet)
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
            
            # Создаем инлайн кнопки
            from telegram import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
            import os
            web_app_url = os.getenv('WEB_APP_URL', 'https://synthosaicreativestudio-maker.github.io/marketing/')
            # Добавляем версию для сброса кеша Telegram WebView
            version = "v=20260107-4"
            menu_url = (
                f"{web_app_url}menu.html?{version}"
                if web_app_url.endswith('/')
                else f"{web_app_url}/menu.html?{version}"
            )
            
            # Формируем кнопки: сначала ссылка (если есть), потом мини-приложение
            buttons = []
            if promotion.get('link') and promotion['link'].strip():
                buttons.append([InlineKeyboardButton(
                    "📎 Перейти к материалам",
                    url=promotion['link'].strip()
                )])
            buttons.append([InlineKeyboardButton(
                "📋 Посмотреть все акции", 
                web_app=WebAppInfo(url=menu_url)
            )])
            reply_markup = InlineKeyboardMarkup(buttons)
            
            # Проверяем наличие медиа-контента
            content_url = promotion.get('content', '').strip()
            has_media = content_url and content_url != 'None' and content_url != ''
            
            # Определяем тип медиа по расширению или URL
            is_photo = False
            is_video = False
            if has_media:
                content_lower = content_url.lower()
                photo_extensions = ('.jpg', '.jpeg', '.png', '.gif', '.webp', '.svg')
                video_extensions = ('.mp4', '.mov', '.avi', '.mkv', '.webm')
                
                # Проверка по расширению файла
                has_photo_extension = any(content_lower.endswith(ext) for ext in photo_extensions)
                has_video_extension = any(content_lower.endswith(ext) for ext in video_extensions)
                
                # Проверка на известные хостинги изображений (как в menu.html)
                is_image_hosting = (
                    'googleusercontent.com' in content_lower or
                    'drive.google.com' in content_lower or
                    'googleapis.com' in content_lower or
                    'imgur.com' in content_lower or
                    'imgbb.com' in content_lower or
                    'cloudinary.com' in content_lower
                )
                
                if has_photo_extension or 'photo' in content_lower or 'image' in content_lower or (is_image_hosting and not has_video_extension):
                    is_photo = True
                elif has_video_extension or 'video' in content_lower:
                    is_video = True
            
            # Отправляем уведомления всем пользователям
            sent_count = 0
            for user_id in users:
                try:
                    if has_media and is_photo:
                        # Отправляем фото с подписью
                        await self.bot.send_photo(
                            chat_id=user_id,
                            photo=content_url,
                            caption=message,
                            parse_mode='Markdown',
                            reply_markup=reply_markup
                        )
                        logger.info(f"Уведомление о акции '{promotion['title']}' с фото отправлено пользователю {user_id}")
                    elif has_media and is_video:
                        # Отправляем видео с подписью
                        await self.bot.send_video(
                            chat_id=user_id,
                            video=content_url,
                            caption=message,
                            parse_mode='Markdown',
                            reply_markup=reply_markup
                        )
                        logger.info(f"Уведомление о акции '{promotion['title']}' с видео отправлено пользователю {user_id}")
                    else:
                        # Отправляем обычное текстовое сообщение
                        await self.bot.send_message(
                            chat_id=user_id,
                            text=message,
                            parse_mode='Markdown',
                            reply_markup=reply_markup
                        )
                        logger.info(f"Уведомление о акции '{promotion['title']}' отправлено пользователю {user_id}")
                    
                    sent_count += 1
                    
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
        if self.is_running:
            logger.warning("Мониторинг акций уже запущен")
            return
        
        self.is_running = True
        logger.info(f"Запуск мониторинга акций (проверка каждые {interval_minutes} минут)")
        
        self._task = asyncio.create_task(self._monitoring_loop(interval_minutes))
    
    async def stop_monitoring(self):
        """Останавливает мониторинг акций"""
        if not self.is_running:
            return
        
        self.is_running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        
        logger.info("Мониторинг акций остановлен")
    
    async def _monitoring_loop(self, interval_minutes: int):
        """Основной цикл мониторинга"""
        while self.is_running:
            try:
                await self.check_and_send_notifications()
                await asyncio.sleep(interval_minutes * 60)
            except asyncio.CancelledError:
                logger.info("Мониторинг акций отменён")
                break
            except Exception as e:
                logger.error(f"Ошибка в мониторинге акций: {e}", exc_info=True)
                await asyncio.sleep(60)  # Ждем минуту при ошибке
