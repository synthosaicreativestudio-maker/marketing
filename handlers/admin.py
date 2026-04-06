import os
import logging
import asyncio
import re
import shlex
from typing import Optional
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler

from error_handler import safe_handler
from ai_service import AIService

logger = logging.getLogger(__name__)

BOT_SERVICE_NAME = os.getenv("BOT_SERVICE_NAME", "marketingbot-bot.service")
OPENCLAW_SERVICE_NAME = os.getenv("OPENCLAW_SERVICE_NAME", "openclaw-gateway.service")
_AI_SERVICE: Optional[AIService] = None

def _is_admin(user_id: int) -> bool:
    admin_id = os.getenv("ADMIN_TELEGRAM_ID", "284355186").strip()
    return admin_id.isdigit() and int(admin_id) == user_id

def register_admin_handlers(application, ai_service: AIService = None):
    global _AI_SERVICE
    _AI_SERVICE = ai_service

    # Старые команды
    if ai_service:
        application.add_handler(CommandHandler("rag_refresh", rag_refresh_handler(ai_service)))
        application.add_handler(CommandHandler("reload_prompt", reload_prompt_handler(ai_service)))
    
    # Новое интерактивное расширенное меню
    application.add_handler(CommandHandler("admin", admin_menu_handler))
    application.add_handler(CallbackQueryHandler(admin_callback_handler, pattern="^admin_"))


def _build_admin_menu() -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton("🔄 Обновить промпт", callback_data="admin_update_prompt"),
            InlineKeyboardButton("🧹 Сброс памяти", callback_data="admin_clear_memory"),
        ],
        [
            InlineKeyboardButton("📊 Статус ИИ", callback_data="admin_ai_status"),
            InlineKeyboardButton("💻 Состояние сервера", callback_data="admin_sys_status"),
        ],
        [
            InlineKeyboardButton("⚙️ Конфигурация ИИ", callback_data="admin_config_menu"),
        ],
        [
            InlineKeyboardButton("⚠️ Перезапуск бота", callback_data="admin_restart_ai"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def _resolve_bot_env_file() -> str:
    repo_env = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
    candidates = [
        os.getenv("BOT_ENV_FILE", "").strip(),
        "/home/marketing/shared/.env",
        repo_env,
    ]
    for candidate in candidates:
        if candidate and os.path.exists(candidate):
            return candidate
    return repo_env


def _read_env_file(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8") as file_obj:
            return file_obj.read()
    except FileNotFoundError:
        return ""


def _write_env_file(path: str, text: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as file_obj:
        file_obj.write(text.rstrip() + "\n")


def _get_env_flag(path: str, key: str, default: bool = False) -> bool:
    text = _read_env_file(path)
    match = re.search(rf"(?m)^\s*{re.escape(key)}\s*=\s*(.+?)\s*$", text)
    if not match:
        return default
    return match.group(1).strip().lower() in {"1", "true", "yes", "y", "on"}


def _set_env_flag(path: str, key: str, enabled: bool) -> None:
    text = _read_env_file(path)
    value = "true" if enabled else "false"
    pattern = re.compile(rf"(?m)^\s*{re.escape(key)}\s*=.*$")
    line = f"{key}={value}"
    if pattern.search(text):
        text = pattern.sub(line, text)
    else:
        if text and not text.endswith("\n"):
            text += "\n"
        text += f"{line}\n"
    _write_env_file(path, text)


async def _get_service_status(service_name: str) -> str:
    try:
        process = await asyncio.create_subprocess_exec(
            "systemctl",
            "is-active",
            service_name,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await process.communicate()
        status = stdout.decode().strip()
        return status or "inactive"
    except FileNotFoundError:
        return "systemctl-unavailable"
    except Exception as exc:
        logger.error("Failed to get service status for %s: %s", service_name, exc)
        return "unknown"


async def _trigger_bot_restart() -> None:
    command = (
        f"nohup sh -lc 'sleep 1; sudo systemctl restart {shlex.quote(BOT_SERVICE_NAME)}' "
        "> /dev/null 2>&1 &"
    )
    await asyncio.create_subprocess_shell(command)


@safe_handler
async def admin_menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not _is_admin(user.id):
        await update.message.reply_text("⛔ Доступ запрещен. Вы не являетесь администратором.")
        return

    await update.message.reply_text(
        "🛠 **Панель администратора ИИ**\n\nВыберите действие:",
        reply_markup=_build_admin_menu(),
        parse_mode="Markdown",
    )


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
    
    elif action == "admin_back":
        await query.edit_message_text(
            "🛠 **Панель администратора ИИ**\n\nВыберите действие:",
            reply_markup=_build_admin_menu(),
            parse_mode="Markdown",
        )
    
    elif action.startswith("admin_toggle_"):
        await _toggle_config(query, action.replace("admin_toggle_", ""))

    elif action == "admin_update_prompt":
        await query.edit_message_text("📥 Обновляю системный промпт...")
        if not _AI_SERVICE:
            await query.edit_message_text("❌ AIService не инициализирован.")
            return
        try:
            import datetime
            refreshed = await _AI_SERVICE.refresh_system_prompt(force=True)
            if refreshed:
                svc = getattr(_AI_SERVICE, "service", None) or _AI_SERVICE
                prompt_text = getattr(svc, "system_prompt", "") or ""
                char_count = len(prompt_text)
                preview = prompt_text[:120].replace("\n", " ").strip()
                now = datetime.datetime.now().strftime("%d.%m.%Y %H:%M:%S")
                await query.edit_message_text(
                    f"✅ *Промпт обновлён*\n\n"
                    f"🕐 Время: `{now}`\n"
                    f"📊 Символов: `{char_count}`\n"
                    f"🔤 Начало:\n`{preview}...`",
                    parse_mode="Markdown",
                )
            else:
                await query.edit_message_text("⚠️ Не удалось обновить промпт.")
        except Exception as exc:
            logger.error("Prompt refresh failed: %s", exc, exc_info=True)
            await query.edit_message_text(f"❌ Ошибка обновления промпта: {exc}")


    elif action == "admin_ai_status":
        await query.edit_message_text("📊 Сбор статусов ИИ интеграций...")
        env_path = _resolve_bot_env_file()
        bot_status = await _get_service_status(BOT_SERVICE_NAME)
        lines = []

        if _AI_SERVICE:
            enabled = _AI_SERVICE.is_enabled()
            lines.append(
                f"{'🟢' if enabled else '🔴'} Backend: {_AI_SERVICE.get_backend_name()}"
            )
            lines.append(f"ℹ️ Провайдер: {_AI_SERVICE.get_provider_name()}")
        else:
            lines.append("🔴 Backend: AIService unavailable")

        lines.append(f"{'🟢' if bot_status == 'active' else '🔴'} Bot Service: {bot_status}")
        lines.append(
            "🌐 Google Search: "
            f"{'enabled' if _get_env_flag(env_path, 'ENABLE_GOOGLE_SEARCH') else 'disabled'}"
        )
        lines.append(f"🧾 Env file: {env_path}")

        if _AI_SERVICE and _AI_SERVICE.get_backend_name() == "openclaw_legacy":
            openclaw_status = await _get_service_status(OPENCLAW_SERVICE_NAME)
            lines.append(
                f"{'🟢' if openclaw_status == 'active' else '🔴'} OpenClaw Gateway: {openclaw_status}"
            )

        await query.edit_message_text(
            "**Статус ИИ:**\n\n" + "\n".join(lines),
            parse_mode="Markdown",
        )

    elif action == "admin_sys_status":
        await query.edit_message_text("💻 Анализ состояния сервера (US Server)...")
        script = "echo 'CPU Load: '$(uptime | awk -F'load average:' '{print $2}') && free -m | awk 'NR==2{printf \"RAM Usage: %sMB / %sMB (%.2f%%)\\n\", $3,$2,$3*100/$2 }' && df -h / | awk 'NR==2{printf \"Disk Usage: %s / %s (%s)\\n\", $3,$2,$5}'"
        process = await asyncio.create_subprocess_shell(script, stdout=asyncio.subprocess.PIPE)
        stdout, _ = await process.communicate()
        await query.edit_message_text(f"**Состояние Сервера:**\n\n`{stdout.decode().strip()}`", parse_mode="Markdown")

    elif action == "admin_clear_memory":
        if _AI_SERVICE:
            _AI_SERVICE.clear_history(user.id)
            await query.edit_message_text("🧹 История текущего диалога очищена.")
        else:
            await query.edit_message_text("⚠️ AIService недоступен, очищать нечего.")

    elif action == "admin_restart_ai":
        await query.edit_message_text(
            f"⚠️ Перезапускаю сервис `{BOT_SERVICE_NAME}`...",
            parse_mode="Markdown",
        )
        await _trigger_bot_restart()


async def _show_config_menu(query):
    """Отображение меню конфигурации полномочий."""
    env_path = _resolve_bot_env_file()
    enable_search = _get_env_flag(env_path, "ENABLE_GOOGLE_SEARCH")
    backend_name = _AI_SERVICE.get_backend_name() if _AI_SERVICE else os.getenv("AI_BACKEND", "direct_gemini")

    k_search = "🟢 Включен" if enable_search else "🔴 Выключен"

    keyboard = [
        [InlineKeyboardButton(f"🌐 Интернет серфинг: {k_search}", callback_data="admin_toggle_search")],
        [InlineKeyboardButton("⬅️ Назад", callback_data="admin_back")]
    ]
    
    await query.edit_message_text(
        "⚙️ **Конфигурация ИИ**\n\n"
        f"Backend: `{backend_name}`\n"
        f"Env file: `{env_path}`\n\n"
        "Переключатель ниже меняет только разрешение на Google Search. "
        "Backend выбирается через переменную `AI_BACKEND` в env.",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

async def _toggle_config(query, feature: str):
    await query.answer("Обработка...")
    
    if feature == "search":
        try:
            env_path = _resolve_bot_env_file()
            enabled = _get_env_flag(env_path, "ENABLE_GOOGLE_SEARCH")
            _set_env_flag(env_path, "ENABLE_GOOGLE_SEARCH", not enabled)
        except Exception as e:
            logger.error(f"Search toggle failed: {e}")
            await query.edit_message_text(f"❌ Не удалось обновить env: {e}")
            return

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
        await ai_service.refresh_system_prompt(force=True)
        await update.message.reply_text("Готово.")
    return handler
