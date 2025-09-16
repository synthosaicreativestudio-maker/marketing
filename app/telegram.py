import hashlib
import hmac
import json
import logging
import urllib.parse
from typing import Optional

logger = logging.getLogger(__name__)


def parse_init_data(init_data: str) -> dict[str, str]:
    """Parse Telegram WebApp initData (URL query-like string) into a dict.

    Handles URL-encoded values and returns a mapping key->single value
    (first value if repeated).
    """
    out: dict[str, str] = {}
    if not init_data:
        return out
    # parse_qs gives lists; values may be percent-encoded JSON
    parsed = urllib.parse.parse_qs(init_data, keep_blank_values=True)
    for k, v in parsed.items():
        if not v:
            out[k] = ''
        else:
            out[k] = v[0]
    return out


def validate_init_data(init_data: str, bot_token: str) -> bool:
    """Validate initData signature using bot token per Telegram docs.

    Uses SHA256(bot_token) as secret_key and HMAC-SHA256 over the data_check_string.
    Returns True if signature valid, False otherwise.
    """
    try:
        data = parse_init_data(init_data)
        hash_received = data.pop('hash', None)
        if not hash_received:
            logger.debug('validate_init_data: no hash present')
            return False
        items = [f"{k}={v}" for k, v in sorted(data.items())]
        data_check_string = '\n'.join(items)
        secret_key = hashlib.sha256(bot_token.encode()).digest()
        hmac_calc = hmac.new(
            secret_key, data_check_string.encode(), hashlib.sha256
        ).hexdigest()
        # use compare_digest for timing-attack resistance
        return hmac.compare_digest(hmac_calc, hash_received)
    except Exception as e:
        logger.exception('validate_init_data error: %s', e)
        return False


def extract_telegram_id(init_data: str) -> Optional[int]:
    """Try to extract Telegram user id from init_data.

    init_data may contain a `user` field which is JSON (possibly URL-encoded),
    or may contain `user_id` or plain numeric `id` field.
    Returns int user id or None.
    """
    try:
        data = parse_init_data(init_data)
        # direct numeric fields
        for key in ('user_id', 'id'):
            if key in data and data[key].isdigit():
                return int(data[key])

        user_field = data.get('user')
        if not user_field:
            return None

        # decode if percent-encoded
        decoded = urllib.parse.unquote_plus(user_field)
        # if looks like JSON, parse
        if decoded.startswith('{'):
            j = json.loads(decoded)
            if isinstance(j, dict):
                if 'id' in j and (isinstance(j['id'], int) or str(j['id']).isdigit()):
                    return int(j['id'])
                # nested user
                if 'user' in j and isinstance(j['user'], dict) and 'id' in j['user']:
                    return int(j['user']['id'])
        # try plain int fallback
        if user_field.isdigit():
            return int(user_field)
    except Exception:
        logger.exception('extract_telegram_id failed')
    return None
