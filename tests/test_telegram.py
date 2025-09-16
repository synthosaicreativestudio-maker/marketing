import hashlib
import hmac
import json
import time
import urllib.parse

from app import telegram as tg


def make_initdata_for_test(bot_token: str, user: dict):
    params = {
        'user': json.dumps(user, separators=(',', ':')),
        'auth_date': str(int(time.time()))
    }
    items = sorted(params.items())
    data_check_string = '\n'.join(f"{k}={v}" for k, v in items)
    secret_key = hashlib.sha256(bot_token.encode()).digest()
    mac = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    params['hash'] = mac
    return '&'.join(f"{k}={urllib.parse.quote_plus(v)}" for k, v in params.items())


def test_parse_and_extract():
    bot_token = 'test-token-123'  # nosec B105
    user = {'id': 99999, 'first_name': 'Unit'}
    initdata = make_initdata_for_test(bot_token, user)
    parsed = tg.parse_init_data(initdata)
    if 'user' not in parsed:
        raise AssertionError("'user' key not found in parsed data")
    uid = tg.extract_telegram_id(initdata)
    if uid != 99999:
        raise AssertionError(f"Expected uid 99999, got {uid}")


def test_validate_initdata():
    test_bot_token_alt = 'another-token'  # nosec B105
    bot_token = test_bot_token_alt
    user = {'id': 5}
    initdata = make_initdata_for_test(bot_token, user)
    if tg.validate_init_data(initdata, bot_token) is not True:
        raise AssertionError("Expected init data to be valid")
    # tamper with data
    bad = initdata.replace('auth_date=', 'auth_date=1')
    if tg.validate_init_data(bad, bot_token) is not False:
        raise AssertionError("Expected tampered init data to be invalid")
