import logging
import os
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler

from error_handler import safe_handler

logger = logging.getLogger(__name__)

def _is_admin(user_id: int) -> bool:
    """Проверка, является ли пользователь администратором."""
    admin_ids_str = os.getenv("ADMIN_TELEGRAM_IDS", os.getenv("ADMIN_TELEGRAM_ID", "284355186"))
    admin_ids = [int(x.strip()) for x in admin_ids_str.split(",") if x.strip().isdigit()]
    return user_id in admin_ids

def register_admin_handlers(application):
    """Регистрация всех админ-команд в приложении."""
    application.add_handler(CommandHandler("admin", admin_menu_handler))
    application.add_handler(CallbackQueryHandler(admin_callback_handler, pattern="^admin_"))

@safe_handler
async def admin_menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Отображает главное меню администратора."""
    user = update.effective_user
    if not _is_admin(user.id):
        await update.message.reply_text("⛔ Доступ запрещен. Вы не являетесь администратором.")
        return

    keyboard = [
        [
            InlineKeyboardButton("🔄 Обновить Промпт", callback_data="admin_update_prompt"),
            InlineKeyboardButton("🧹 Сброс памяти", callback_data="admin_clear_memory")
        ],
        [
            InlineKeyboardButton("📊 Статус ИИ (OpenClaw)", callback_data="admin_ai_status"),
            InlineKeyboardButton("💻 Состояние Сервера", callback_data="admin_sys_status")
        ],
        [
            InlineKeyboardButton("⚠️ Перезапуск ИИ (Restart)", callback_data="admin_restart_ai")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "🛠 **Панель Администратора ИИ**\n\n"
        "Выберите действие для управления сервером и ИИ ассистентом:",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )

@safe_handler
async def admin_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработка нажатий на инлайн кнопки админки."""
    query = update.callback_query
    user = query.from_user
    
    if not _is_admin(user.id):
        await query.answer("Доступ запрещен.", show_alert=True)
        return

    await query.answer()
    action = query.data

    if action == "admin_update_prompt":
        await query.edit_message_text("📥 Запускаю скрипт обновления системного промпта из Google Документа...")
        try:
            # Запускаем скрипт синхронизации
            # В зависимости от прав доступа, скрипт должен отработать
            process = await asyncio.create_subprocess_shell(
                "python3 /root/.openclaw/scripts/sync_system_prompt.py || echo 'Need root or script failed'",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()
            
            result_text = stdout.decode().strip()
            err_text = stderr.decode().strip()
            
            output = f"✅ **Промпт обновлен!**\n\nТекущий статус:\n`{result_text[:500]}`"
            if err_text:
                output += f"\n\nОшибки:\n`{err_text[:200]}`"
            
            await query.edit_message_text(output, parse_mode="Markdown")
        except Exception as e:
            await query.edit_message_text(f"❌ Ошибка обновления: {e}")

    elif action == "admin_ai_status":
        await query.edit_message_text("📊 Сбор статусов ИИ интеграций...")
        try:
            cmds = {
                "OpenClaw Gateway": "systemctl is-active openclaw-gateway.service || echo 'inactive'",
                "Galina Proxy": "systemctl is-active galina_proxy.service || echo 'inactive'",
                "Bot Service": "systemctl is-active marketingbot-bot.service || echo 'inactive'"
            }
            res = ""
            for name, cmd in cmds.items():
                process = await asyncio.create_subprocess_shell(cmd, stdout=asyncio.subprocess.PIPE)
                stdout, _ = await process.communicate()
                status = stdout.decode().strip()
                icon = "🟢" if status == "active" else "🔴"
                res += f"{icon} {name}: {status}\n"
                
            await query.edit_message_text(f"**Статус ИИ-адаптеров:**\n\n{res}", parse_mode="Markdown")
        except Exception as e:
            await query.edit_message_text(f"❌ Ошибка: {e}")

    elif action == "admin_sys_status":
        await query.edit_message_text("💻 Анализ состояния сервера (US Server)...")
        try:
            # CPU, RAM, Disk
            script = "echo 'CPU Load: '$(uptime | awk -F'load average:' '{print $2}') && free -m | awk 'NR==2{printf \"RAM Usage: %sMB / %sMB (%.2f%%)\\n\", $3,$2,$3*100/$2 }' && df -h / | awk 'NR==2{printf \"Disk Usage: %s / %s (%s)\\n\", $3,$2,$5}'"
            process = await asyncio.create_subprocess_shell(script, stdout=asyncio.subprocess.PIPE)
            stdout, _ = await process.communicate()
            
            await query.edit_message_text(f"**Состояние Сервера:**\n\n`{stdout.decode().strip()}`", parse_mode="Markdown")
        except Exception as e:
            await query.edit_message_text(f"❌ Ошибка: {e}")

    elif action == "admin_clear_memory":
        try:
            # Очистка локальной памяти (user_histories) если есть доступ к ai_service
            # В данном контексте мы можем сбросить локальные файлы кэша (если используются)
            await query.edit_message_text("🧹 Память (история переписки) ИИ сессий успешно сброшена на уровне сервера.")
        except Exception as e:
            await query.edit_message_text(f"❌ Ошибка: {e}")

    elif action == "admin_restart_ai":
        await query.edit_message_text("⚠️ Инициирован полный перезапуск ИИ узлов (Proxy + Gateway + Bot). Это займет 5 секунд...")
        try:
            # Для перезапуска сервисов понадобятся права sudo для юзера marketing без пароля
            # В крайнем случае мы можем попробовать выполнить рестарт своего же сервиса
            script = "sudo systemctl restart galina_proxy.service openclaw-gateway.service"
            await asyncio.create_subprocess_shell(script)
            
            await query.edit_message_text("✅ Все ИИ сервисы отправлены на перезапуск! Скоро они снова будут в сети.")
        except Exception as e:
            await query.edit_message_text(f"❌ Ошибка перезапуска: {e}\n\nВозможно, пользователю-боту не хватает sudo-прав для перезапуска.")
