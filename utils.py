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

    # Сначала конвертируем Markdown в HTML с экранированием
    text = _markdown_to_telegram_html(text)
    
    # Затем форматируем ссылки, которые ИИ мог прислать "голыми"
    text = _format_links_safe(text)

    return text


def sanitize_ai_text_plain(text: str, ensure_emojis: bool = True) -> str:
    """Возвращает чистый plain-text без Markdown/HTML, ссылки формата 'Название: URL'."""
    if not text:
        return text

    # First, handle AI hallucinations where it wraps its text in <think ... >
    # This safely deletes the "<think" prefix and closing ">" but KEEPS the text inside!
    text = re.sub(r'<think\s+(.*?)>', r'\1 ', text)
    text = text.replace("<think>", "").replace("</think>", "").replace("<think", "")
    
    # Remove remaining HTML tags, but ONLY standard ones (to avoid aggressively deleting text if model hallucinates < )
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


def _convert_markdown_links(text: str) -> str:
    # [Текст](https://example.com) -> Текст — https://example.com
    return re.sub(r'\[([^\]]+)\]\((https?://[^\s)]+)\)', r'\1 — \2', text)


def _format_links(text: str) -> str:
    url_re = re.compile(r'https?://[^\s\)\]\}>]+')
    lines = text.splitlines()
    out_lines = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            out_lines.append(line)
            continue

        urls = url_re.findall(stripped)
        if not urls:
            out_lines.append(line)
            continue

        # Если строка — это только ссылка(и)
        if stripped in urls or stripped.rstrip(".,;") in urls:
            if len(urls) == 1:
                out_lines.append(f"Ссылка — {urls[0]}")
            else:
                for u in urls:
                    out_lines.append(f"Ссылка — {u}")
            continue

        # Иначе берем первую ссылку и делаем "Текст — URL"
        url = urls[0]
        label = stripped.replace(url, "").strip()
        label = re.sub(r'[:—–-]+$', '', label).strip()
        if not label:
            label = "Ссылка"
        out_lines.append(f"{label} — {url}")

    return "\n".join(out_lines)


def _strip_markdown(text: str) -> str:
    # Убираем только символы, которые могут сломать некоторые интерфейсы 
    # (но оставляем жирный, курсив и заголовки для Телеграма)
    text = text.replace("```", "")
    text = text.replace("`", "")
    return text


def _normalize_whitespace(text: str) -> str:
    lines = []
    for line in text.splitlines():
        line = re.sub(r"[ \t]+", " ", line).strip()
        lines.append(line)
    return "\n".join(lines).strip()


def _ensure_emojis(text: str) -> str:
    """Оставляет текст как есть. Логика принудительных эмодзи перенесена в промпт."""
    return text


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

def _is_user_escalation_request(text: str) -> bool:
    """
    Проверяет, содержит ли сообщение пользователя триггерные слова для эскалации.
    """
    import re
    
    # Нормализуем текст: убираем знаки препинания и приводим к нижнему регистру
    text_normalized = re.sub(r'[^\w\s]', '', text.lower())
    
    # Прямые триггерные фразы для эскалации (30 фраз)
    escalation_phrases = [
        'хочу поговорить со специалистом',
        'нужен специалист',
        'передайте специалисту',
        'соедините с менеджером',
        'соедините с специалистом',
        'хочу к человеку',
        'живой человек',
        'реальный специалист',
        'дайте мне специалиста',
        'дайте специалиста',
        'хочу специалиста',
        'нужен человек',
        'хочу к специалисту',
        'нужен маркетолог',
        'хочу маркетолога',
        'дайте маркетолога',
        'нужен специалист по маркетингу',
        'хочу специалиста по маркетингу',
        'дайте специалиста по маркетингу',
        'нужен специалист отдела маркетинга',
        'хочу специалиста отдела маркетинга',
        'дайте специалиста отдела маркетинга',
        'передайте мой вопрос',
        'передайте мою проблему',
        'передайте мое обращение',
        'эскалируйте вопрос',
        'эскалируйте проблему',
        'эскалируйте обращение',
        'хочу поговорить с человеком',
        'дайте человека'
    ]
    
    # Проверяем наличие триггерных фраз в нормализованном тексте
    for phrase in escalation_phrases:
        if phrase in text_normalized:
            return True
    
    return False

def _is_ai_asking_for_escalation(ai_response: str) -> bool:
    """
    Проверяет, спрашивает ли ИИ о необходимости передачи специалисту.
    """
    if not ai_response:
        return False
        
    response_lower = ai_response.lower()
    
    # Фразы, когда ИИ спрашивает об эскалации
    escalation_questions = [
        'нужно ли передать',
        'передать специалисту',
        'соединить со специалистом',
        'связать со специалистом',
        'передать ваш запрос',
        'передать вашу проблему',
        'передать ваше обращение',
        'эскалировать вопрос',
        'эскалировать проблему',
        'эскалировать обращение',
        'передать менеджеру',
        'соединить с менеджером',
        'связать с менеджером',
        'передать маркетологу',
        'соединить с маркетологом',
        'связать с маркетологом',
        # Фразы из system_prompt.txt (реальные ответы ИИ)
        'передам вашу задачу специалисту',
        'передам задачу специалисту',
        'передам запрос специалисту',
        'передаю ваш запрос',
        'передам его специалисту',
        'зафиксирую запрос и передам',
        'свяжется с вами',
        'он свяжется с вами',
    ]
    
    # Проверяем наличие вопросов об эскалации
    for phrase in escalation_questions:
        if phrase in response_lower:
            return True
    
    return False

def _is_escalation_confirmation(text: str) -> bool:
    """
    Проверяет, содержит ли сообщение подтверждение эскалации к специалисту.
    """
    text_lower = text.lower()
    
    # Фразы подтверждения эскалации (когда ИИ спрашивает)
    confirmation_phrases = [
        'да',
        'да, нужно',
        'да, передайте',
        'да, соедините',
        'да, свяжите',
        'да, пожалуйста',
        'да, конечно',
        'да, давайте',
        'да, хорошо',
        'да, согласен',
        'нужно',
        'передайте',
        'соедините',
        'свяжите',
        'пожалуйста',
        'конечно',
        'давайте',
        'хорошо',
        'согласен',
        'подтверждаю'
    ]
    
    # Проверяем наличие фраз подтверждения
    for phrase in confirmation_phrases:
        if phrase in text_lower:
            return True
    
    return False

def _should_show_specialist_button(text: str) -> bool:
    """
    Проверяет, просит ли пользователь соединить его со специалистом/живым человеком.
    """
    text_lower = text.lower()
    
    # Ключевые фразы, которые указывают на желание поговорить со специалистом
    specialist_keywords = [
        'специалист', 'специалиста', 'специалисту', 'специалистом',
        'живой человек', 'живому человеку', 'живым человеком',
        'менеджер', 'менеджера', 'менеджеру', 'менеджером',
        'сотрудник', 'сотрудника', 'сотруднику', 'сотрудником',
        'оператор', 'оператора', 'оператору', 'оператором',
        'консультант', 'консультанта', 'консультанту', 'консультантом',
        'соединить', 'соедините', 'соедини', 'соединиться',
        'поговорить', 'поговорить с', 'поговорить с человеком',
        'человек', 'человека', 'человеку', 'человеком',
        'позвонить', 'позвоните', 'звонок', 'звонить',
        'связаться', 'связаться с', 'связать', 'связать с',
        'поддержка', 'поддержку', 'поддержке', 'поддержкой',
        'помощь', 'помощи', 'помочь', 'помощью',
        'не могу', 'не получается', 'не работает',
        'проблема', 'проблемы', 'проблему', 'проблемой',
        'сложно', 'сложный', 'сложная', 'сложное',
        'не понимаю', 'не понятно', 'не ясно',
        'объясните', 'объясни', 'объяснить',
        'подробнее', 'подробно', 'подробный',
        'детали', 'детализация', 'детально'
    ]
    
    # Проверяем наличие ключевых слов
    for keyword in specialist_keywords:
        if keyword in text_lower:
            return True
    
    return False

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
