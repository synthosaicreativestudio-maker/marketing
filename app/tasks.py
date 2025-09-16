import os

from redis import Redis
from rq import Queue


def get_redis_conn():
    redis_url = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')
    return Redis.from_url(redis_url)


def enqueue_send_message(telegram_id: int, text: str):
    conn = get_redis_conn()
    q = Queue('default', connection=conn)
    # import here to avoid circular imports
    from app.bot_helper import _send_sync
    job = q.enqueue(_send_sync, os.environ.get('TELEGRAM_BOT_TOKEN'), telegram_id, text)
    return job
