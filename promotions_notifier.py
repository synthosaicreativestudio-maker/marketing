import logging
import asyncio
import io
import base64
import requests
from typing import List, Dict, Optional
from urllib.parse import urlparse, parse_qs

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
        
    async def _prepare_media(self, content_url: str) -> Optional[io.BytesIO]:
        """Подготавливает медиа-файл в памяти (BytesIO).
        
        ТЗ 2.1: Поддержка Base64, Google Drive и прямых ссылок с кешированием.
        """
        if not content_url or content_url == 'None' or not content_url.strip():
            return None

        content_url = content_url.strip()
        
        try:
            # Сценарий А: Base64
            if content_url.startswith('data:image'):
                logger.debug("Detected Base64 image")
                header, encoded = content_url.split(",", 1)
                data = base64.b64decode(encoded)
                return io.BytesIO(data)

            # Сценарий Б: Google Drive
            if 'drive.google.com' in content_url:
                logger.debug(f"Detected Google Drive link: {content_url}")
                file_id = None
                if '/file/d/' in content_url:
                    file_id = content_url.split('/file/d/')[1].split('/')[0]
                elif 'id=' in content_url:
                    parsed_url = urlparse(content_url)
                    file_id = parse_qs(parsed_url.query).get('id', [None])[0]
                
                if file_id:
                    # Конвертируем в формат скачивания (ТЗ 2.1.Б)
                    download_url = f"https://drive.google.com/uc?export=download&id={file_id}"
                    logger.info(f"Downloading from Google Drive: {download_url}")
                    
                    # Используем таймаут 15 сек и маршрут через US (requests подхватит системный прокси)
                    response = requests.get(download_url, timeout=15)
                    response.raise_for_status()
                    
                    # Проверка размера (ТГ лимит ~10МБ для фото, но ТЗ допускает до 20МБ)
                    if len(response.content) > 20 * 1024 * 1024:
                        logger.warning(f"File from Drive is too large: {len(response.content)} bytes")
                        return None
                        
                    return io.BytesIO(response.content)

            # Сценарий В: Прямая ссылка
            if content_url.startswith('http'):
                logger.debug(f"Detected direct URL: {content_url}")
                response = requests.get(content_url, timeout=15)
                response.raise_for_status()
                
                if len(response.content) > 20 * 1024 * 1024:
                    logger.warning(f"File from URL is too large: {len(response.content)} bytes")
                    return None
                    
                return io.BytesIO(response.content)

            return None
            
        except Exception as e:
            logger.error(f"Failed to prepare media from {content_url[:50]}...: {e}")
            return None

    async def _send_promotion_notification(self, promotion: Dict, users: List[int]):
        """Отправляет уведомление о новой акции пользователям (Блок Б)"""
        try:
            # 1. Формируем сообщение
            title = promotion.get('title', 'Акция')
            description = promotion.get('description', '')
            msg_text = "🎉 **Новая акция!**\n\n"
            msg_text += f"**{title}**\n\n"
            msg_text += f"📝 {description[:200]}{'...' if len(description) > 200 else ''}\n\n"
            msg_text += f"📅 **Период действия:** {promotion.get('start_date', '?')} - {promotion.get('end_date', '?')}\n\n"
            
            # 2. Подготавливаем кнопки
            from telegram import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
            import os
            web_app_url = os.getenv('WEB_APP_URL', 'https://synthosaicreativestudio-maker.github.io/marketing/')
            version = "v=20260107-4"
            menu_url = f"{web_app_url.rstrip('/')}/menu.html?{version}"
            
            buttons = []
            if promotion.get('link') and promotion['link'].strip():
                buttons.append([InlineKeyboardButton("📎 Перейти к материалам", url=promotion['link'].strip())])
            buttons.append([InlineKeyboardButton("📋 Посмотреть все акции", web_app=WebAppInfo(url=menu_url))])
            reply_markup = InlineKeyboardMarkup(buttons)
            
            # 3. Кеширование Медиа (ТЗ 2.1): Подготавливаем ОДИН РАЗ перед рассылкой
            content_url = promotion.get('content', '').strip()
            media_data = await self._prepare_media(content_url)
            
            is_error_media = content_url and (not media_data) and content_url != 'None'
            if is_error_media:
                msg_text += "\n⚠️ _(Изображение недоступно)_"
            
            # 4. Рассылка
            sent_count = 0
            for user_id in users:
                try:
                    if media_data:
                        # Сбрасываем указатель для каждого нового пользователя
                        media_data.seek(0)
                        await self.bot.send_photo(
                            chat_id=user_id,
                            photo=media_data,
                            caption=msg_text,
                            parse_mode='Markdown',
                            reply_markup=reply_markup
                        )
                    else:
                        await self.bot.send_message(
                            chat_id=user_id,
                            text=msg_text,
                            parse_mode='Markdown',
                            reply_markup=reply_markup
                        )
                    
                    sent_count += 1
                    await asyncio.sleep(0.1) # Защита от Flood
                    
                except Exception as e:
                    logger.warning(f"Не удалось отправить уведомление пользователю {user_id}: {e}")
            
            logger.info(f"Акция '{title}' доставлена {sent_count}/{len(users)} пользователям")
            
        except Exception as e:
            logger.error(f"Критическая ошибка рассылки акции: {e}", exc_info=True)

    async def check_and_send_notifications(self):
        """Проверяет новые акции и отправляет уведомления"""
        if not await is_promotions_available(self.gateway):
            return
            
        try:
            new_promotions = await check_new_promotions(self.gateway)
            if not new_promotions:
                return
                
            authorized_users = await self._get_authorized_users()
            if not authorized_users:
                return
                
            for promotion in new_promotions:
                if promotion['id'] not in self.sent_promotions:
                    await self._send_promotion_notification(promotion, authorized_users)
                    self.sent_promotions.add(promotion['id'])
                    
        except Exception as e:
            logger.error(f"Ошибка при проверке уведомлений: {e}")
    
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
            return authorized_users
        except Exception as e:
            logger.error(f"Ошибка получения юзеров: {e}")
            return []

    async def start_monitoring(self, interval_minutes: int = 15):
        """Запускает мониторинг новых акций"""
        if self.is_running:
            return
        self.is_running = True
        logger.info(f"Запуск мониторинга акций ({interval_minutes} мин)")
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
    
    async def _monitoring_loop(self, interval_minutes: int):
        """Основной цикл мониторинга"""
        while self.is_running:
            try:
                await self.check_and_send_notifications()
                await asyncio.sleep(interval_minutes * 60)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Ошибка в цикле мониторинга: {e}")
                await asyncio.sleep(60)
