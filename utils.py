import os
import logging
import re
from urllib.parse import urlparse
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, MenuButtonDefault

logger = logging.getLogger(__name__)


async def alert_admin(bot, message: str, level: str = "ERROR") -> bool:
    """
    Отправляет критическое уведомление админу в Telegram.
    
    Args:
        bot: Экземпляр Telegram бота
        message: Текст уведомления
        level: Уровень (ERROR, CRITICAL, WARNING)
    
    Returns:
        True если сообщение отправлено, False если произошла ошибка
    """
    admin_id = os.getenv("ADMIN_TELEGRAM_ID")
    if not admin_id:
        logger.warning("ADMIN_TELEGRAM_ID не настроен, алерт не отправлен")
        return False
    
    emoji = {"ERROR": "⚠️", "CRITICAL": "🚨", "WARNING": "⚡"}.get(level, "ℹ️")
    
    try:
        await bot.send_message(
            chat_id=admin_id,
            text=f"{emoji} {level}\n\n{message}"
        )
        logger.info(f"Алерт отправлен админу: {message[:50]}...")
        return True
    except Exception as e:
        logger.error(f"Не удалось отправить алерт админу: {e}")
        return False


def sanitize_ai_text(text: str, ensure_emojis: bool = True) -> str:
    """Очищает ответ ИИ от Markdown/служебных символов и приводит ссылки к виду 'Название — URL'."""
    if not text:
        return text

    # 1. Удаляем все теги рассуждений ДО экранирования HTML
    text = _strip_reasoning_tags(text)

    # 2. Конвертируем Markdown в HTML с экранированием
    text = _markdown_to_telegram_html(text)
    
    # 3. Форматируем ссылки, которые ИИ мог прислать "голыми"
    text = _format_links_safe(text)

    return text


def sanitize_ai_text_plain(text: str, ensure_emojis: bool = True) -> str:
    """Возвращает чистый plain-text без Markdown/HTML, ссылки формата 'Название: URL'."""
    if not text:
        return text

    # 1. Единая очистка reasoning-тегов
    text = _strip_reasoning_tags(text)
    
    # Remove remaining HTML tags, but ONLY standard ones
    text = re.sub(r"</?(b|strong|i|em|a|code|pre|s|u)[^>]*>", "", text, flags=re.IGNORECASE)

    # Convert markdown links to "Text: URL"
    text = re.sub(r'\[([^\]]+)\]\((https?://[^\s)]+)\)', r'\1: \2', text)

    # Удаление формальных фраз ОТКЛЮЧЕНО, чтобы бот мог следовать промпту
    # text = re.sub(r'(?i)\bсогласно (?:нашей )?базе знаний[^.]*\.\s*', '', text)

    # Strip markdown formatting markers
    text = text.replace("```", "")
    text = text.replace("`", "")
    text = text.replace("**", "")
    text = text.replace("__", "")
    text = re.sub(r'(?m)^#{1,6}\s*', '', text)
    text = re.sub(r'(?m)^\s*[\-\*\+]\s+', '', text)

    text = _normalize_whitespace(text)
    return text

def safe_truncate_html(text: str, limit: int = 3900) -> str:
    """
    Безопасно обрезает HTML-строку для Telegram, не разрывая теги <... >.
    Если разрез попадает внутрь тега, обрезает до начала этого тега.
    """
    if len(text) <= limit:
        return text
    
    # Обрезаем по лимиту
    truncated = text[:limit]
    
    # Ищем последнее вхождение '<'
    last_open_bracket = truncated.rfind('<')
    if last_open_bracket != -1:
        # Проверяем, закрыт ли этот тег внутри обрезанной строки
        if '>' not in truncated[last_open_bracket:]:
            # Тег не закрыт, обрезаем ДО '<'
            return truncated[:last_open_bracket]
            
    return truncated


def _markdown_to_telegram_html(text: str) -> str:
    """Конвертирует Markdown-разметку Gemini в HTML для Telegram с экранированием."""
    if not text:
        return ""
    
    # 0. Экранируем спецсимволы HTML
    text = text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

    # 1. Жирный текст: **text** -> <b>text</b>
    text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', text)
    text = re.sub(r'__(.*?)__', r'<b>\1</b>', text)
    
    # 2. Курсив: *text* -> <i>text</i>
    text = re.sub(r'(?<!\*)\*(?!\*)(.*?)(?<!\*)\*(?!\*)', r'<i>\1</i>', text)
    
    # 3. Ссылки: [Text](URL) -> <a href="URL">Text</a>
    # Telegram требует 'href="URL"', причем URL уже содержит &amp; после шага 0.
    text = re.sub(r'\[([^&\]]+)\]\((https?://[^\s)]+)\)', r'<a href="\2">\1</a>', text)
    
    # 4. Заголовки: ### Header -> <b>Header</b>
    text = re.sub(r'^#{1,6}\s+(.*)$', r'<b>\1</b>', text, flags=re.MULTILINE)
    
    return text

def _format_links_safe(text: str) -> str:
    """Безопасно форматирует голые URL, не ломая уже созданные <a> теги."""
    # Регулярка для URL, которые НЕ внутри href="..."
    url_re = re.compile(r'(?<!href=")(https?://[^\s\)\]\}>]+)')
    
    def repl(match):
        url = match.group(1)
        # Если это чистый URL в тексте, превратим его в кликабельную ссылку "Источник"
        # или просто оставим как есть, но в HTML Telegram он должен быть внутри <a> если мы хотим анкор.
        # Для стабильности просто обернем его в <a> если он не слишком длинный
        if len(url) < 100:
            return f'<a href="{url}">ссылка</a>'
        return url

    return url_re.sub(repl, text)

def _strip_reasoning_tags(text: str) -> str:
    """Удаляет ВСЕ reasoning-теги и их содержимое из ответа ИИ.
    
    Обрабатывает: <think>, <thinking>, <final>, <final_answer>, <thought>, 
    и их вариации с атрибутами.
    """
    if not text:
        return text
    
    # 1. Удаляем ПОЛНЫЕ блоки с содержимым: <think>...</think>, <thinking>...</thinking>,
    #    <final>...</final>, <final_answer>...</final_answer>, <thought>...</thought>
    text = re.sub(
        r'<(?:think(?:ing)?|final(?:_answer)?|thought)[^>]*>.*?</(?:think(?:ing)?|final(?:_answer)?|thought)\s*>',
        '', text, flags=re.IGNORECASE | re.DOTALL
    )
    
    # 2. Удаляем НЕЗАКРЫТЫЕ блоки (если поток оборвался внутри тега)
    text = re.sub(
        r'<(?:think(?:ing)?|final(?:_answer)?|thought)[^>]*>.*$',
        '', text, flags=re.IGNORECASE | re.DOTALL
    )
    
    # 3. Удаляем одиночные теги (открывающие и закрывающие)
    text = re.sub(
        r'</?(?:think(?:ing)?|final(?:_answer)?|thought)\s*[^>]*>',
        '', text, flags=re.IGNORECASE
    )
    
    return text.strip()

def _normalize_whitespace(text: str) -> str:
    lines = []
    for line in text.splitlines():
        line = re.sub(r"[ \t]+", " ", line).strip()
        lines.append(line)
    return "\n".join(lines).strip()


def _is_ai_asking_for_escalation(ai_response: str) -> bool:
    """
    Проверяет, предлагает ли ИИ передачу специалисту в своём ответе.
    """
    if not ai_response:
        return False

    response_lower = ai_response.lower()

    escalation_phrases = [
        'передам вашу задачу специалисту',
        'передам задачу специалисту',
        'передам запрос специалисту',
        'передаю ваш запрос',
        'передам его специалисту',
        'зафиксирую запрос и передам',
        'свяжется с вами',
        'он свяжется с вами',
        'передать специалисту',
        'соединить со специалистом',
        'связать со специалистом',
        'передать менеджеру',
        'передать маркетологу',
    ]

    for phrase in escalation_phrases:
        if phrase in response_lower:
            return True

    return False




def mask_phone(phone: str) -> str:
    """Маскирует номер телефона: 89123456789 -> 8*******89."""
    if not phone or not str(phone).strip():
        return "****"
    s = str(phone).strip()
    if len(s) < 4:
        return "****"
    return s[:1] + "*" * (len(s) - 3) + s[-2:]


def mask_telegram_id(tid) -> str:
    """Маскирует Telegram ID: 123456789 -> 123***789."""
    if tid is None:
        return "***"
    s = str(tid)
    if len(s) < 6:
        return "***"
    return s[:3] + "***" + s[-3:]


def mask_fio(fio: str) -> str:
    """Маскирует ФИО: Иванов Иван Иванович -> И***в И***н И***ч."""
    if not fio or not str(fio).strip():
        return "***"
    parts = str(fio).strip().split()
    masked = []
    for part in parts:
        if len(part) < 3:
            masked.append("***")
        else:
            masked.append(part[0] + "*" * (len(part) - 2) + part[-1])
    return " ".join(masked)


def _validate_url(url: str) -> bool:
    """Проверяет, является ли строка валидным URL."""
    if not url:
        return False
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except Exception:
        return False

def get_web_app_url() -> str:
    """Ленивое чтение URL WebApp из окружения (после загрузки .env)."""
    base_url = os.getenv("WEB_APP_URL") or ""
    
    # Валидация URL
    if base_url and not _validate_url(base_url):
        logger.error(f"WEB_APP_URL содержит невалидный URL: {base_url}")
        return ""
    
    if base_url and not base_url.endswith('/'):
        base_url += '/'
    url = base_url + "index.html"
    logger.debug(f"Generated WebApp URL: {url}")
    return url

def get_spa_menu_url() -> str:
    """Ленивое чтение URL SPA меню из окружения."""
    base_url = os.getenv("WEB_APP_URL") or ""
    # Версия для принудительного обновления кеша WebApp
    cache_bust = "v=20260107-4"
    
    # Валидация URL
    if base_url and not _validate_url(base_url):
        logger.error(f"WEB_APP_URL содержит невалидный URL: {base_url}")
        return ""
    
    if base_url and not base_url.endswith('/'):
        base_url += '/'
    url = f"{base_url}menu.html?{cache_bust}"
    logger.debug(f"Generated SPA Menu URL: {url}")
    return url

def create_specialist_button() -> InlineKeyboardMarkup:
    """
    Создает инлайн-кнопку для обращения к специалисту.
    """
    keyboard = [[InlineKeyboardButton("👨‍💼 ОБРАТИТЬСЯ К СПЕЦИАЛИСТУ", callback_data="contact_specialist")]]
    return InlineKeyboardMarkup(keyboard)



async def set_dynamic_menu_button(bot, chat_id: int, is_authorized: bool = False):
    """
    Сбрасывает динамическую кнопку меню (Menu Button) для пользователя в стандартное состояние.
    Мы перешли на использование ReplyKeyboardMarkup для всех действий.
    """
    try:
        await bot.set_chat_menu_button(
            chat_id=chat_id,
            menu_button=MenuButtonDefault()
        )
        logger.debug(f"Menu button reset to default for {chat_id}")
    except Exception as e:
        logger.error(f"Failed to reset menu button for {chat_id}: {e}")
