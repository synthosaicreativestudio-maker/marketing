import logging
import os
import time
from threading import Thread
from typing import Optional

logger = logging.getLogger(__name__)

# optional prometheus metrics for messaging
try:
    from prometheus_client import Counter
    BOT_MESSAGES = Counter('bot_messages_total', 'Total bot message attempts')
    BOT_MESSAGE_FAILURES = Counter(
        'bot_message_failures_total', 'Total failed bot messages'
    )
except Exception:
    class _Noop:
        def inc(self, *a, **k):
            return None

    BOT_MESSAGES = _Noop()
    BOT_MESSAGE_FAILURES = _Noop()


def _send_sync(token: str, telegram_id: int, text: str) -> bool:
    try:
        # Use requests to send message via Telegram Bot API (synchronous)
        import requests
        
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        data = {
            "chat_id": telegram_id,
            "text": text
        }
        
        response = requests.post(url, json=data, timeout=30)
        response.raise_for_status()
        return True
    except Exception as e:
        logger.exception('send_message failed: %s', e)
        return False


def send_message_to(
    telegram_id: Optional[int], text: str, retries: int = 3,
    backoff: float = 1.0, background: bool = False
) -> bool:
    token = os.environ.get('TELEGRAM_BOT_TOKEN')
    if not token or not telegram_id:
        logger.debug('No token or telegram_id; skip send')
        return False
    BOT_MESSAGES.inc()
    # If REDIS_URL provided, enqueue the send job and return immediately
    if os.environ.get('REDIS_URL'):
        try:
            from app.tasks import enqueue_send_message
            enqueue_send_message(telegram_id, text)
            logger.info('Enqueued send message to %s', telegram_id)
            return True
        except Exception as e:
            logger.exception('Failed to enqueue send job: %s', e)
            # fallthrough to direct send

    def _worker() -> bool:
        attempt = 0
        while True:
            attempt += 1
            ok = _send_sync(token, telegram_id, text)
            if ok:
                logger.info('Message sent to %s', telegram_id)
                return True
            if attempt >= retries:
                logger.error(
                    'Failed to send message to %s after %s attempts',
                    telegram_id, attempt
                )
                return False
            sleep = backoff * (2 ** (attempt - 1))
            time.sleep(sleep)

    if background:
        Thread(target=_worker, daemon=True).start()
        return True
    else:
        return _worker()
