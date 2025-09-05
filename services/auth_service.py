# -*- coding: utf-8 -*-
"""
Сервис для обработки всей логики, связанной с авторизацией пользователей.
"""

import os
import logging
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, WebAppInfo
from telegram.ext import ContextTypes
from pydantic import ValidationError

from auth_cache import auth_cache
from config import get_web_app_url
from schemas import AuthRequest

class AuthService:
    def __init__(self, sheets_client, run_blocking_func):
        self.logger = logging.getLogger('marketing_bot.auth_service')
        self.sheets_client = sheets_client
        self.run_blocking = run_blocking_func

    def is_admin(self, user_id: int) -> bool:
        admin_ids = os.getenv('ADMIN_TELEGRAM_ID', '')
        if not admin_ids:
            return False
        admin_list = [s.strip() for s in admin_ids.split(',') if s.strip()]
        return str(user_id) in admin_list

    def create_auth_keyboard(self, url: str):
        return ReplyKeyboardMarkup(
            [[KeyboardButton('🔐 Авторизоваться', web_app=WebAppInfo(url=url))]],
            resize_keyboard=True,
            one_time_keyboard=False
        )

    async def is_user_authorized(self, user_id: int) -> bool:
        cached_auth = auth_cache.is_user_authorized(user_id)
        if cached_auth is not None:
            return cached_auth
        try:
            authorized_ids = await self.run_blocking(self.get_authorized_ids)
            if authorized_ids is None:
                return False
            is_auth = str(user_id) in authorized_ids
            auth_cache.set_user_authorized(user_id, is_auth)
            return is_auth
        except Exception as e:
            self.logger.error(f"Ошибка проверки авторизации для {user_id}: {e}")
            return False

    def get_authorized_ids(self):
        cached_ids = auth_cache.get_authorized_ids()
        if cached_ids is not None:
            return cached_ids
        try:
            if not self.sheets_client or not self.sheets_client.sheet:
                return None
            ids = self.sheets_client.get_all_authorized_user_ids()
            auth_cache.set_authorized_ids(set(str(i) for i in ids if i))
            return auth_cache.get_authorized_ids()
        except Exception as e:
            self.logger.error(f"Не удалось получить ID: {e}")
            return None

    async def auth_command_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        args = context.args
        if len(args) != 2:
            await update.message.reply_text('Неверный формат. Используйте: /auth <код> <телефон>')
            return
        
        payload = {"type": "auth_request", "code": args[0], "phone": args[1]}
        await self.handle_auth_from_webapp(update, context, payload)

    async def handle_auth_from_webapp(self, update: Update, context: ContextTypes.DEFAULT_TYPE, payload: dict):
        user = update.effective_user
        try:
            auth_data = AuthRequest(**payload)
        except ValidationError as e:
            self.logger.warning(f"Некорректные данные авторизации от {user.id}: {e.errors()}")
            await update.message.reply_text('❌ Ошибка валидации данных. Пожалуйста, попробуйте еще раз.')
            return

        is_blocked, seconds_left = auth_cache.is_user_blocked(user.id)
        if is_blocked:
            time_text = self._format_block_time(seconds_left)
            await update.message.reply_text(f'❌ Авторизация заблокирована на {time_text}.')
            return

        await update.message.reply_text('🔍 Проверяю данные...')

        if not self.sheets_client or not self.sheets_client.sheet:
            self.logger.error('Google Sheets client not available')
            await update.message.reply_text('База недоступна. Свяжитесь с админом.')
            return

        try:
            row = await self.run_blocking(self.sheets_client.find_user_by_credentials, auth_data.code, auth_data.phone)
        except Exception as e:
            self.logger.error(f"Ошибка проверки данных: {e}")
            await update.message.reply_text('Ошибка проверки данных. Попробуйте позже.')
            return

        if row:
            await self._handle_successful_authorization(update, context, row, auth_data.code, auth_data.phone)
        else:
            await self._handle_failed_authorization(update, context)

    def _format_block_time(self, seconds: int) -> str:
        hours = seconds // 3600
        if hours > 24:
            days = hours // 24
            return f"{days} дн{'я' if days < 5 else 'ей'}"
        if hours > 0:
            return f"{hours} час{'а' if hours < 5 else 'ов'}"
        minutes = (seconds % 3600) // 60
        return f"{minutes} минут"

    async def _handle_successful_authorization(self, update: Update, context: ContextTypes.DEFAULT_TYPE, row: int, code: str, phone: str):
        user = update.effective_user
        try:
            await self.run_blocking(self.sheets_client.update_user_auth_status, row, user.id)
            context.user_data['is_authorized'] = True
            context.user_data['partner_code'] = code
            context.user_data['phone'] = phone
            auth_cache.clear_failed_attempts(user.id)
            self.logger.info(f"Авторизация для пользователя {user.id} прошла успешно.")
            await update.message.reply_text('✅ Авторизация прошла успешно!')
        except Exception as e:
            self.logger.error(f"Ошибка при сохранении авторизации: {e}")
            await update.message.reply_text('Ошибка при сохранении авторизации. Попробуйте позже.')
            raise

    async def _handle_failed_authorization(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        is_blocked, block_duration = auth_cache.add_failed_attempt(user.id)
        if is_blocked:
            time_text = self._format_block_time(block_duration)
            await update.message.reply_text(f'❌ Авторизация заблокирована на {time_text}.')
        else:
            attempts_left = auth_cache.get_attempts_left(user.id)
            web_app_url = get_web_app_url('MAIN')
            keyboard = self.create_auth_keyboard(web_app_url)
            await update.message.reply_text(
                f'❌ Неверные данные или аккаунт неактивен.\nОсталось попыток: {attempts_left}',
                reply_markup=keyboard
            )