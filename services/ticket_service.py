# -*- coding: utf-8 -*-
"""
Сервис для обработки сообщений, тикетов и взаимодействия с OpenAI.
"""

import logging
import collections.abc
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import ContextTypes

from config import get_web_app_url
from openai_client import openai_client
from mcp_context_v7 import mcp_context

class TicketService:
    def __init__(self, auth_service, tickets_client, run_blocking_func, bot):
        self.logger = logging.getLogger('marketing_bot.ticket_service')
        self.auth_service = auth_service
        self.tickets_client = tickets_client
        self.run_blocking = run_blocking_func
        self.bot = bot

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await self._log_incoming_message(update, context)

        if not openai_client.is_available():
            await update.message.reply_text('OpenAI недоступен.')
            return

        try:
            assistant_msg = await self._get_openai_response(update, context)
            if not assistant_msg:
                await update.message.reply_text('Ошибка ответа от ассистента.')
                return

            buttons = await self._create_ticket_buttons(update, context)
            assistant_msg_text = self._extract_text_from_response(assistant_msg)

            await self._send_response(update, assistant_msg_text, buttons)
            await self._log_assistant_response(update, context, assistant_msg_text)
        except Exception as e:
            self.logger.exception(f"Ошибка при обработке сообщения: {e}")
            await update.message.reply_text('Произошла ошибка.')

    async def _log_incoming_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            if self.tickets_client and self.tickets_client.sheet:
                user = update.effective_user
                text = update.message.text
                await self.run_blocking(
                    self.tickets_client.upsert_ticket,
                    str(user.id), context.user_data.get('partner_code', ''),
                    context.user_data.get('phone', ''), f"{user.first_name or ''} {user.last_name or ''}".strip(),
                    text, 'в работе', 'user', False
                )
        except Exception as e:
            self.logger.error(f"Не удалось записать входящее сообщение в tickets: {e}")

    async def _get_openai_response(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> str | None:
        user = update.effective_user
        text = update.message.text
        user_data = {
            'partner_code': context.user_data.get('partner_code', ''),
            'telegram_id': str(user.id)
        }
        thread_id = await openai_client.get_or_create_thread(user_data)
        if not thread_id:
            self.logger.error("Не удалось создать или получить thread_id для OpenAI.")
            return None
        mcp_context.register_thread(thread_id, user_data['telegram_id'])
        mcp_context.append_message(thread_id, 'user', text)
        assistant_msg = await openai_client.send_message(thread_id, text)
        if assistant_msg:
            mcp_context.append_message(thread_id, 'assistant', str(assistant_msg))
            mcp_context.prune_thread(thread_id, keep=80)
        return assistant_msg

    async def _create_ticket_buttons(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> list | None:
        try:
            user = update.effective_user
            code = context.user_data.get('partner_code', '')
            row = None
            if code and self.tickets_client:
                row = await self.run_blocking(self.tickets_client.find_row_by_code, code)
            if not row and self.tickets_client:
                cell = await self.run_blocking(self.tickets_client.sheet.find, str(user.id), in_column=4)
                row = cell.row if cell else None
            if row:
                return [
                    [InlineKeyboardButton('Перевести специалисту', callback_data=f't:transfer:{row}'), InlineKeyboardButton('Выполнено', callback_data=f't:done:{row}')],
                    [InlineKeyboardButton('Личный кабинет', web_app=WebAppInfo(url=get_web_app_url('SPA_MENU')))]
                ]
        except Exception as e:
            self.logger.warning(f"Не удалось создать кнопки для тикета: {e}")
        return None

    def _extract_text_from_response(self, response: any) -> str:
        if response is None: return ''
        if isinstance(response, str): return response
        if isinstance(response, bytes):
            try: return response.decode('utf-8')
            except Exception: return ''
        if isinstance(response, collections.abc.Mapping):
            parts = [self._extract_text_from_response(v) for v in response.values()]
            return '\n'.join(p for p in parts if p)
        if isinstance(response, collections.abc.Iterable) and not isinstance(response, (str, bytes)):
            parts = [self._extract_text_from_response(el) for el in response]
            return '\n'.join(p for p in parts if p)
        for attr in ['text', 'content', 'value', 'message', 'output_text']:
            if hasattr(response, attr):
                val = getattr(response, attr)
                t = self._extract_text_from_response(val)
                if t: return t
        s = str(response)
        if s.startswith('<') and s.endswith('>'): return ''
        if s and s != repr(response): return s
        return ''

    async def _send_response(self, update: Update, text: str, buttons: list | None):
        if 'annotations value' in text:
            text = text.replace('annotations value', '')
        self.logger.info(f"Отправка ответа пользователю. Наличие кнопок: {buttons is not None}. Сообщение: {text[:100]}...")
        reply_markup = InlineKeyboardMarkup(buttons) if buttons else None
        await update.message.reply_text(text, reply_markup=reply_markup)

    async def _log_assistant_response(self, update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
        try:
            if self.tickets_client and self.tickets_client.sheet:
                user = update.effective_user
                await self.run_blocking(
                    self.tickets_client.upsert_ticket,
                    str(user.id), context.user_data.get('partner_code', ''),
                    context.user_data.get('phone', ''), f"{user.first_name or ''} {user.last_name or ''}".strip(),
                    text, 'в работе', 'assistant', False
                )
        except Exception as e:
            self.logger.error(f"Не удалось записать ответ ассистента в tickets: {e}")

    async def handle_callback_query(self, query: Update.callback_query, context: ContextTypes.DEFAULT_TYPE):
        data = query.data
        parts = data.split(':')
        if len(parts) != 3:
            await query.edit_message_text('Некорректный формат действия с тикетом.')
            return
        action = parts[1]
        try:
            row = int(parts[2])
        except (ValueError, IndexError):
            await query.edit_message_text('Неверный идентификатор тикета.')
            return
        if action == 'transfer':
            await self._transfer_ticket(query, context, row)
        elif action == 'done':
            await self._mark_ticket_as_done(query, row)
        else:
            await query.edit_message_text('Неизвестное действие с тикетом.')

    async def _transfer_ticket(self, query, context: ContextTypes.DEFAULT_TYPE, row: int):
        try:
            ok = await self.run_blocking(self.tickets_client.set_ticket_status, row, None, 'в работе')
            if ok:
                await query.edit_message_reply_markup(None)
                await query.edit_message_text('Тикет помечен как "в работе" и направлен специалистам.')
                await self._notify_specialists(context, row)
            else:
                await query.edit_message_text('Не удалось изменить статус (ошибка записи).')
        except Exception as e:
            self.logger.error(f"Ошибка при переводе тикета специалисту: {e}")
            await query.edit_message_text('Произошла ошибка при переводе тикета.')

    async def _mark_ticket_as_done(self, query, row: int):
        try:
            ok = await self.run_blocking(self.tickets_client.set_ticket_status, row, None, 'выполнено')
            if ok:
                await query.edit_message_reply_markup(None)
                await query.edit_message_text('Тикет помечен как выполнено.')
            else:
                await query.edit_message_text('Не удалось пометить тикет как выполнено.')
        except Exception as e:
            self.logger.error(f"Ошибка при пометке тикета как выполненного: {e}")
            await query.edit_message_text('Произошла ошибка при обновлении статуса тикета.')

    async def _notify_specialists(self, context: ContextTypes.DEFAULT_TYPE, row: int):
        # ... (logic from bot.py)
        pass

    async def reply_command_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        # ... (logic from bot.py)
        pass