# -*- coding: utf-8 -*-
"""
Сервис для всей логики, связанной с акциями.
"""

import logging
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import ContextTypes

from config import PROMOTIONS_CONFIG, get_web_app_url

class PromotionsService:
    def __init__(self, auth_service, async_promotions_client, sheets_client, run_blocking_func, bot):
        self.logger = logging.getLogger('marketing_bot.promotions_service')
        self.auth_service = auth_service
        self.async_promotions_client = async_promotions_client
        self.sheets_client = sheets_client # For getting authorized users
        self.run_blocking = run_blocking_func
        self.bot = bot

    async def test_promotions_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Тестовая команда для проверки функциональности акций.
        """
        user = update.effective_user
        self.logger.info(f"/test_promotions от {user.id} ({user.first_name})")
        
        if not await self.auth_service.is_user_authorized(user.id):
            await update.message.reply_text('Вы не авторизованы. Сначала пройдите авторизацию.')
            return
            
        await update.message.reply_text('🔍 Тестирую подключение к таблице акций...')
        
        try:
            if not self.async_promotions_client:
                await update.message.reply_text('❌ Асинхронный клиент акций не инициализирован')
                return
            
            if not self.async_promotions_client.sheet:
                connected = await self.async_promotions_client.connect()
                if not connected:
                    await update.message.reply_text('❌ Не удалось подключиться к таблице акций')
                    return
            
            new_promotions = await self.async_promotions_client.get_new_published_promotions()
            active_promotions = await self.async_promotions_client.get_active_promotions()
            
            result_text = f'''✅ Подключение к таблице акций работает!

📊 Статистика:
🆕 Новых для уведомления: {len(new_promotions)}
🎯 Активных всего: {len(active_promotions)}

⏰ Мониторинг: каждые {PROMOTIONS_CONFIG['MONITORING_INTERVAL']} секунд
🔄 Последняя проверка: прошла успешно'''
            
            if new_promotions:
                result_text += "\n\n🎉 Новые акции:\n"
                for promo in new_promotions[:3]:
                    name = promo.get('name', 'Без названия')
                    result_text += f"• {name}\n"
            
            await update.message.reply_text(result_text)
            
        except Exception as e:
            self.logger.error(f"Ошибка в тесте акций: {e}")
            await update.message.reply_text(f'❌ Ошибка при тестировании: {str(e)}')

    async def handle_get_promotions_api(self, update: Update, context: ContextTypes.DEFAULT_TYPE, payload: dict):
        """
        Обрабатывает API запрос на получение акций для мини-приложения.
        """
        user = update.effective_user
        self.logger.info(f"📱 API запрос акций от пользователя {user.id} ({user.first_name})")
        
        try:
            if not self.async_promotions_client:
                self.logger.warning("Асинхронный клиент акций не инициализирован")
                await self._send_promotions_response(update, [])
                return
            
            if not self.async_promotions_client.sheet:
                connected = await self.async_promotions_client.connect()
                if not connected:
                    self.logger.warning("Не удалось подключиться к таблице акций")
                    await self._send_promotions_response(update, [])
                    return
            
            active_promotions = await self.async_promotions_client.get_active_promotions()
            
            self.logger.info(f"📋 Получено {len(active_promotions)} активных акций для мини-приложения")
            await self._send_promotions_response(update, active_promotions)
                
        except Exception as e:
            self.logger.error(f"❌ Ошибка при обработке API запроса акций: {e}")
            await self._send_promotions_response(update, [])
    
    async def _send_promotions_response(self, update_or_query, promotions: list):
        """
        Отправляет ответ с акциями в мини-приложение.
        """
        try:
            if hasattr(update_or_query, 'message'):
                message = update_or_query.message
            else:
                message = update_or_query
            
            await message.reply_text(
                f"📱 Данные акций отправлены в мини-приложение\n\n🎉 Найдено {len(promotions)} активных акций",
                reply_markup=InlineKeyboardMarkup([[ 
                    InlineKeyboardButton(
                        "🔄 Обновить акции", 
                        web_app=WebAppInfo(url=get_web_app_url('SPA_MENU'))
                    )
                ]])
            )
            
            self.logger.info(f"✅ Отправлен ответ с {len(promotions)} акциями в мини-приложение")
            
        except Exception as e:
            self.logger.error(f"❌ Ошибка отправки ответа акций: {e}")
            # Error reporting to user is handled by the main bot class

    async def monitor_new_promotions(self, context: ContextTypes.DEFAULT_TYPE):
        """
        Мониторинг новых опубликованных акций для отправки уведомлений.
        """
        self.logger.info("🔍 Проверяем новые акции...")
        
        if not self.async_promotions_client:
            self.logger.warning("❌ Клиент акций не инициализирован, мониторинг пропущен")
            return
            
        try:
            if not self.async_promotions_client.sheet:
                self.logger.info("🔗 Подключаемся к таблице акций для мониторинга...")
                connected = await self.async_promotions_client.connect()
                if not connected:
                    self.logger.warning("❌ Не удалось подключиться к таблице акций, мониторинг пропущен")
                    return
            
            new_promotions = await self.async_promotions_client.get_new_published_promotions()
            
            if not new_promotions:
                self.logger.info("📭 Новых акций для уведомления не найдено")
                return
                
            self.logger.info(f"🎉 Найдено {len(new_promotions)} новых акций для уведомления")
            
            authorized_users = await self.get_authorized_users()
            
            if not authorized_users:
                self.logger.warning("Нет авторизованных пользователей для отправки уведомлений об акциях")
                return
            
            for promotion in new_promotions:
                try:
                    await self._send_promotion_notification(context, promotion, authorized_users)
                    await self.async_promotions_client.mark_notification_sent(promotion['row'])
                    await asyncio.sleep(PROMOTIONS_CONFIG['NOTIFICATION_DELAY'])
                except Exception as e:
                    self.logger.error(f"❌ Ошибка при отправке уведомления об акции '{promotion.get('name', 'Unknown')}': {e}")
                    continue
                    
        except Exception as e:
            self.logger.error(f"❌ Ошибка в мониторинге новых акций: {e}")
    
    async def _send_promotion_notification(self, context: ContextTypes.DEFAULT_TYPE, promotion: dict, authorized_users: list):
        """
        Отправляет уведомление о новой акции всем авторизованным пользователям.
        """
        try:
            name = promotion.get('name', 'Новая акция')
            description = promotion.get('description', '')
            start_date = promotion.get('start_date')
            end_date = promotion.get('end_date')
            
            max_desc_length = PROMOTIONS_CONFIG['MAX_DESCRIPTION_LENGTH']
            if description and len(description) > max_desc_length:
                description = description[:max_desc_length] + '...'
            
            period_text = ''
            if start_date and end_date:
                period_text = f"📅 Действует: {start_date.strftime('%d.%m.%Y')} - {end_date.strftime('%d.%m.%Y')}"
            elif start_date:
                period_text = f"📅 Начало: {start_date.strftime('%d.%m.%Y')}"
            
            message_text = f"""🎉 Новая акция опубликована!

📢 {name}
{period_text}

{description if description else 'Подробности в личном кабинете'}

👀 Посмотреть подробнее ↓"""
            
            spa_menu_url = get_web_app_url('SPA_MENU') + '?section=promotions'
            keyboard = InlineKeyboardMarkup([[ 
                InlineKeyboardButton('👀 Ознакомиться подробнее', web_app=WebAppInfo(url=spa_menu_url))
            ]])
            
            sent_count = 0
            failed_count = 0
            
            for user in authorized_users:
                telegram_id = user.get('telegram_id')
                if not telegram_id: continue
                    
                try:
                    await context.bot.send_message(chat_id=int(telegram_id), text=message_text, reply_markup=keyboard)
                    sent_count += 1
                except Exception as e:
                    self.logger.warning(f"Не удалось отправить уведомление пользователю {telegram_id}: {e}")
                    failed_count += 1
                await asyncio.sleep(0.1)
            
            self.logger.info(f"✅ Уведомление об акции '{name}' отправлено: {sent_count} успешно, {failed_count} ошибок")
            
        except Exception as e:
            self.logger.error(f"❌ Ошибка при отправке уведомления об акции: {e}")
            raise
    
    async def get_authorized_users(self) -> list:
        """
        Получает список всех авторизованных пользователей для отправки уведомлений.
        """
        try:
            if not self.sheets_client:
                self.logger.error("sheets_client не инициализирован")
                return []
            
            raw_data = await self.run_blocking(self.sheets_client.get_authorized_users_batch)
            
            if isinstance(raw_data, str):
                self.logger.warning("Получена строка вместо словаря. Попытка десериализации JSON...")
                import json
                try: authorized_users_dict = json.loads(raw_data)
                except Exception as e: 
                    self.logger.error(f"Не удалось декодировать JSON: {e}")
                    return []
            elif isinstance(raw_data, dict):
                authorized_users_dict = raw_data
            else:
                self.logger.error(f"КРИТИЧЕСКАЯ ОШИБКА: Неожиданный тип данных: {type(raw_data)}")
                return []
            
            users_with_telegram = []
            for telegram_id, user_data in authorized_users_dict.items():
                if not isinstance(user_data, dict): continue
                user_obj = {
                    'telegram_id': telegram_id,
                    'code': user_data.get('code', ''),
                    'phone': user_data.get('phone', ''),
                    'fio': user_data.get('fio', '')
                }
                users_with_telegram.append(user_obj)
            
            self.logger.info(f"📋 Найдено {len(users_with_telegram)} авторизованных пользователей с Telegram ID")
            return users_with_telegram
            
        except Exception as e:
            self.logger.error(f"❌ КРИТИЧЕСКАЯ ОШИБКА в get_authorized_users: {e}")
            import traceback
            self.logger.error(f"Полный traceback: {traceback.format_exc()}")
            return []
