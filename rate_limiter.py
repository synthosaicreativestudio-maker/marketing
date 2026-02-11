"""
Rate Limiter — ограничение количества сообщений от пользователя.

Защита от:
- Спама
- Случайного "залипания" кнопки
- DDoS-атак

Использует TTLCache (in-memory) — бесплатно, ~1 МБ на 10,000 пользователей.
"""

import logging
from cachetools import TTLCache
from typing import Tuple
from functools import wraps
from telegram import Update
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)

# Конфигурация лимитов
MAX_MESSAGES_PER_MINUTE = 10  # Максимум сообщений за 60 секунд
TTL_SECONDS = 60  # Окно в секундах
CACHE_MAX_USERS = 10000  # Максимум пользователей в кэше

# TTLCache: ключ = user_id, значение = количество сообщений
# Автоматически очищается по истечении TTL
_rate_cache: TTLCache = TTLCache(maxsize=CACHE_MAX_USERS, ttl=TTL_SECONDS)


def check_rate_limit(user_id: int) -> Tuple[bool, int]:
    """
    Проверяет, не превысил ли пользователь лимит сообщений.
    
    Returns:
        Tuple[bool, int]: (разрешено, осталось сообщений)
    """
    current_count = _rate_cache.get(user_id, 0)
    
    if current_count >= MAX_MESSAGES_PER_MINUTE:
        logger.warning(f"Rate limit exceeded for user {user_id} ({current_count}/{MAX_MESSAGES_PER_MINUTE})")
        return False, 0
    
    # Увеличиваем счетчик
    _rate_cache[user_id] = current_count + 1
    remaining = MAX_MESSAGES_PER_MINUTE - current_count - 1
    
    return True, remaining


def rate_limited(func):
    """
    Декоратор для ограничения частоты вызовов обработчика.
    
    Использование:
        @rate_limited
        async def my_handler(update, context):
            ...
    """
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        if not update.effective_user:
            return await func(update, context, *args, **kwargs)
        
        user_id = update.effective_user.id
        allowed, remaining = check_rate_limit(user_id)
        
        if not allowed:
            await update.message.reply_text(
                "⚠️ Слишком много сообщений! Подождите минуту и попробуйте снова."
            )
            return None
        
        # Предупреждение при приближении к лимиту
        if remaining <= 2:
            logger.info(f"User {user_id} approaching rate limit ({remaining} remaining)")
        
        return await func(update, context, *args, **kwargs)
    
    return wrapper


def get_rate_limit_stats() -> dict:
    """Статистика использования rate limiter."""
    return {
        "active_users": len(_rate_cache),
        "max_users": CACHE_MAX_USERS,
        "limit_per_minute": MAX_MESSAGES_PER_MINUTE,
        "ttl_seconds": TTL_SECONDS
    }
