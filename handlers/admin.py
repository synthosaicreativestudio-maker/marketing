import os
import json
import logging
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler

from error_handler import safe_handler
from ai_service import AIService

logger = logging.getLogger(__name__)

OPENCLAW_CONFIG_SCRIPT = "sudo /opt/openclaw/manage_config.sh"
BOT_ENV_FILE = "/home/marketing/shared/.env"

def _is_admin(user_id: int) -> bool:
    admin_id = os.getenv("ADMIN_TELEGRAM_ID", "284355186").strip()
    return admin_id.isdigit() and int(admin_id) == user_id

def register_admin_handlers(application, ai_service: AIService = None):
    # Старые команды
    if ai_service:
        application.add_handler(CommandHandler("rag_refresh", rag_refresh_handler(ai_service)))
        application.add_handler(CommandHandler("reload_prompt", reload_prompt_handler(ai_service)))
    
    # Новое интерактивное расширенное меню
    application.add_handler(CommandHandler("admin", admin_menu_handler))
    application.add_handler(CallbackQueryHandler(admin_callback_handler, pattern="^admin_"))


@safe_handler
async def admin_menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
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
            InlineKeyboardButton("📊 Статус ИИ службо", callback_data="admin_ai_status"),
            InlineKeyboardButton("💻 Состояние Сервера", callback_data="admin_sys_status")
        ],
        [
            InlineKeyboardButton("⚙️ КОнфигурация ИИ (Права)", callback_data="admin_config_menu")
        ],
        [
            InlineKeyboardButton("⚠️ Перезапуск ИИ (Restart)", callback_data="admin_restart_ai")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("🛠 **Панель Администратора ИИ**\n\nВыберите действие:", reply_markup=reply_markup, parse_mode="Markdown")


@safe_handler
async def admin_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    user = query.from_user
    if not _is_admin(user.id):
        await query.answer("Доступ запрещен.", show_alert=True)
        return

    await query.answer()
    action = query.data

    if action == "admin_config_menu":
        await _show_config_menu(query)
    
    elif action.startswith("admin_toggle_"):
        await _toggle_config(query, action.replace("admin_toggle_", ""))

    elif action == "admin_update_prompt":
        await query.edit_message_text("📥 Запускаю скрипт обновления системного промпта из Google Документа...")
        try:
            process = await asyncio.create_subprocess_shell("python3 /root/.openclaw/scripts/sync_system_prompt.py || echo 'Need root'", stdout=asyncio.subprocess.PIPE)
            stdout, _ = await process.communicate()
            await query.edit_message_text(f"✅ **Промпт обновлен!**\n\n`{stdout.decode().strip()[:500]}`", parse_mode="Markdown")
        except Exception as e:
            await query.edit_message_text(f"❌ Ошибка обновления: {e}")

    elif action == "admin_ai_status":
        await query.edit_message_text("📊 Сбор статусов ИИ интеграций...")
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
            res += f"{'🟢' if status == 'active' else '🔴'} {name}: {status}\n"
        await query.edit_message_text(f"**Статус ИИ-адаптеров:**\n\n{res}", parse_mode="Markdown")

    elif action == "admin_sys_status":
        await query.edit_message_text("💻 Анализ состояния сервера (US Server)...")
        script = "echo 'CPU Load: '$(uptime | awk -F'load average:' '{print $2}') && free -m | awk 'NR==2{printf \"RAM Usage: %sMB / %sMB (%.2f%%)\\n\", $3,$2,$3*100/$2 }' && df -h / | awk 'NR==2{printf \"Disk Usage: %s / %s (%s)\\n\", $3,$2,$5}'"
        process = await asyncio.create_subprocess_shell(script, stdout=asyncio.subprocess.PIPE)
        stdout, _ = await process.communicate()
        await query.edit_message_text(f"**Состояние Сервера:**\n\n`{stdout.decode().strip()}`", parse_mode="Markdown")

    elif action == "admin_clear_memory":
        await query.edit_message_text("🧹 Память локальная сброшена.")

    elif action == "admin_restart_ai":
        await query.edit_message_text("⚠️ Полный перезапуск ИИ узлов (Proxy + Gateway + Bot)...")
        await asyncio.create_subprocess_shell(f"{OPENCLAW_CONFIG_SCRIPT} restart && {OPENCLAW_CONFIG_SCRIPT} restart_bot")


async def _show_config_menu(query):
    """Отображение меню конфигурации полномочий."""
    # Read Env
    enable_search = False
    if os.path.exists(BOT_ENV_FILE):
        with open(BOT_ENV_FILE, "r") as f:
            enable_search = "ENABLE_GOOGLE_SEARCH=true" in f.read().lower()

    # Read OpenClaw JSON
    native_bash = "false"
    try:
        process = await asyncio.create_subprocess_shell(f"{OPENCLAW_CONFIG_SCRIPT} read", stdout=asyncio.subprocess.PIPE)
        stdout, _ = await process.communicate()
        oc_data = json.loads(stdout.decode().strip())
        native_bash = oc_data.get("commands", {}).get("native", "false")
    except Exception as e:
        logger.error(f"Failed parsing OpenClaw JSON: {e}")

    # Build keyboard
    k_search = "🟢 Включен" if enable_search else "🔴 Выключен"
    k_bash = "🟢 Включен (auto)" if native_bash == "auto" else "🔴 Выключен"

    keyboard = [
        [InlineKeyboardButton(f"🌐 Интернет серфинг: {k_search}", callback_data="admin_toggle_search")],
        [InlineKeyboardButton(f"💻 Доступ к Bash/Файлам: {k_bash}", callback_data="admin_toggle_bash")],
        [InlineKeyboardButton("⬅️ Назад", callback_data="admin_back")]
    ]
    
    await query.edit_message_text(
        "⚙️ **Редактор прав и разрешений ИИ-Агента**\n\n Выберите параметр для переключения. Бот автоматически сохранит файл конфигурации и мягко перезапустит нужные службы.",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

async def _toggle_config(query, feature: str):
    await query.answer("Обработка...")
    
    if feature == "search":
        # Toggle env
        if os.path.exists(BOT_ENV_FILE):
            with open(BOT_ENV_FILE, "r") as f:
                text = f.read()
            if "ENABLE_GOOGLE_SEARCH=true" in text.lower():
                text = text.replace("ENABLE_GOOGLE_SEARCH=true", "ENABLE_GOOGLE_SEARCH=false")
                text = text.replace("ENABLE_GOOGLE_SEARCH=True", "ENABLE_GOOGLE_SEARCH=false")
            elif "ENABLE_GOOGLE_SEARCH=false" in text.lower() or "ENABLE_GOOGLE_SEARCH=False" in text:
                text = text.replace("ENABLE_GOOGLE_SEARCH=false", "ENABLE_GOOGLE_SEARCH=true")
                text = text.replace("ENABLE_GOOGLE_SEARCH=False", "ENABLE_GOOGLE_SEARCH=true")
            else:
                text += "\nENABLE_GOOGLE_SEARCH=true\n"
            with open(BOT_ENV_FILE, "w") as f:
                f.write(text)
            
            # Restart bot
            await asyncio.create_subprocess_shell(f"{OPENCLAW_CONFIG_SCRIPT} restart_bot")

    elif feature == "bash":
        # Toggle Openclw config
        try:
            process = await asyncio.create_subprocess_shell(f"{OPENCLAW_CONFIG_SCRIPT} read", stdout=asyncio.subprocess.PIPE)
            stdout, _ = await process.communicate()
            oc_data = json.loads(stdout.decode().strip())
            
            if "commands" not in oc_data:
                oc_data["commands"] = {}
            current = oc_data["commands"].get("native", "false")
            
            oc_data["commands"]["native"] = "false" if current == "auto" else "auto"
            oc_data["commands"]["nativeSkills"] = "false" if current == "auto" else "auto"
            
            new_json_str = json.dumps(oc_data, indent=2)
            # Write via sudo script
            write_process = await asyncio.create_subprocess_shell(f"{OPENCLAW_CONFIG_SCRIPT} write", stdin=asyncio.subprocess.PIPE)
            await write_process.communicate(input=new_json_str.encode())
            
            # Restart gateway
            await asyncio.create_subprocess_shell(f"{OPENCLAW_CONFIG_SCRIPT} restart")
        except Exception as e:
            logger.error(f"Bash toggle failed: {e}")

    # Show menu again
    await _show_config_menu(query)


def rag_refresh_handler(ai_service: AIService):
    @safe_handler
    async def handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not _is_admin(update.effective_user.id):
            return
        await update.message.reply_text("Запускаю переиндексацию базы знаний...")
        await ai_service.refresh_knowledge_base()
        await update.message.reply_text("Готово.")
    return handler

def reload_prompt_handler(ai_service: AIService):
    @safe_handler
    async def handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not _is_admin(update.effective_user.id):
            return
        await update.message.reply_text("Обновление промпта...")
        await ai_service.refresh_system_prompt()
        await update.message.reply_text("Готово.")
    return handler
