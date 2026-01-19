"""
Глобальный обработчик ошибок для предотвращения падений бота.
"""
import logging
import functools
import asyncio
from typing import Callable, Any
from telegram.error import (
    TelegramError,
    NetworkError,
    TimedOut,
    RetryAfter,
    Conflict,
    BadRequest,
    Forbidden,
    InvalidToken
)

logger = logging.getLogger(__name__)


def safe_telegram_call(max_retries: int = 3, retry_delay: float = 1.0):
    """
    Декоратор для безопасного вызова Telegram API с автоматическими повторами.
    
    Args:
        max_retries: Максимальное количество попыток
        retry_delay: Задержка между попытками в секундах
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            last_exception = None
            
            for attempt in range(max_retries):
                try:
                    return await func(*args, **kwargs)
                    
                except RetryAfter as e:
                    # Telegram просит подождать
                    wait_time = e.retry_after + retry_delay
                    logger.warning(
                        f"Telegram API rate limit, ожидание {wait_time:.1f} сек "
                        f"(попытка {attempt + 1}/{max_retries})"
                    )
                    await asyncio.sleep(wait_time)
                    last_exception = e
                    continue
                    
                except (NetworkError, TimedOut) as e:
                    # Сетевые ошибки - повторяем
                    if attempt < max_retries - 1:
                        wait_time = retry_delay * (2 ** attempt)  # Exponential backoff
                        logger.warning(
                            f"Сетевая ошибка при вызове {func.__name__}: {e}. "
                            f"Повтор через {wait_time:.1f} сек (попытка {attempt + 1}/{max_retries})"
                        )
                        await asyncio.sleep(wait_time)
                        last_exception = e
                        continue
                    else:
                        logger.error(f"Сетевая ошибка после {max_retries} попыток: {e}")
                        raise
                        
                except Conflict as e:
                    # Конфликт (например, другой экземпляр бота работает)
                    logger.error(f"Конфликт Telegram API: {e}. Возможно, запущен другой экземпляр бота.")
                    raise
                    
                except InvalidToken as e:
                    # Критические ошибки авторизации - не повторяем
                    logger.critical(f"Ошибка авторизации Telegram: {e}")
                    raise
                    
                except (Forbidden, ChatNotFound, BadRequest) as e:
                    # Ошибки клиента - не повторяем, но логируем
                    logger.warning(f"Ошибка клиента Telegram API: {e}")
                    raise
                    
                except TelegramError as e:
                    # Другие ошибки Telegram API
                    if attempt < max_retries - 1:
                        wait_time = retry_delay * (2 ** attempt)
                        logger.warning(
                            f"Ошибка Telegram API при вызове {func.__name__}: {e}. "
                            f"Повтор через {wait_time:.1f} сек (попытка {attempt + 1}/{max_retries})"
                        )
                        await asyncio.sleep(wait_time)
                        last_exception = e
                        continue
                    else:
                        logger.error(f"Ошибка Telegram API после {max_retries} попыток: {e}")
                        raise
                        
                except Exception as e:
                    # Неожиданные ошибки - логируем и пробрасываем
                    logger.error(
                        f"Неожиданная ошибка при вызове {func.__name__}: {e}",
                        exc_info=True
                    )
                    raise
                    
            # Если все попытки исчерпаны
            if last_exception:
                logger.error(
                    f"Не удалось выполнить {func.__name__} после {max_retries} попыток. "
                    f"Последняя ошибка: {last_exception}"
                )
                raise last_exception
                
        return wrapper
    return decorator


def safe_handler(handler_func: Callable) -> Callable:
    """
    Декоратор для безопасной обработки обновлений Telegram.
    Предотвращает падение бота при ошибках в обработчиках.
    """
    @functools.wraps(handler_func)
    async def wrapper(update, context):
        try:
            return await handler_func(update, context)
        except (NetworkError, TimedOut) as e:
            logger.warning(f"Сетевая ошибка в обработчике {handler_func.__name__}: {e}")
            # Не пробрасываем - бот продолжает работу
        except Forbidden as e:
            logger.warning(f"Ошибка доступа в обработчике {handler_func.__name__}: {e}")
            # Не пробрасываем - бот продолжает работу
        except TelegramError as e:
            logger.error(f"Ошибка Telegram API в обработчике {handler_func.__name__}: {e}")
            # Не пробрасываем - бот продолжает работу
        except Exception as e:
            logger.error(
                f"Критическая ошибка в обработчике {handler_func.__name__}: {e}",
                exc_info=True
            )
            # Не пробрасываем - бот продолжает работу
            
    return wrapper
