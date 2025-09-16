import urllib.parse

from app import telegram as tg


def test_extract_from_user_json_unencoded():
    user = {'id': 12345, 'first_name': 'Anna'}
    json_str = __import__('json').dumps(user)
    init = f'user={json_str}&hash=bogus'
    result = tg.extract_telegram_id(init)
    if result != 12345:
        raise AssertionError(f"Expected uid 12345, got {result}")


def test_extract_from_user_json_encoded():
    user = {'id': 54321}
    enc = urllib.parse.quote_plus(__import__('json').dumps(user))
    init = f'user={enc}&hash=bogus'
    result = tg.extract_telegram_id(init)
    if result != 54321:
        raise AssertionError(f"Expected uid 54321, got {result}")


def test_extract_from_user_id_field():
    init = 'user_id=7777&hash=x'
    result = tg.extract_telegram_id(init)
    if result != 7777:
        raise AssertionError(f"Expected uid 7777, got {result}")


def test_extract_from_id_field():
    init = 'id=8888&hash=x'
    result = tg.extract_telegram_id(init)
    if result != 8888:
        raise AssertionError(f"Expected uid 8888, got {result}")


def test_no_user_returns_none():
    result = tg.extract_telegram_id('foo=bar&hash=x')
    if result is not None:
        raise AssertionError(f"Expected None, got {result}")
