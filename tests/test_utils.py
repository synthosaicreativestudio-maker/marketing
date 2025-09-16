from app import sheets
from app import telegram as tg


def test_normalize_phone():
    result = sheets.normalize_phone('+7 (910) 123-45-55')
    if result != '89101234555':
        raise AssertionError(f"Expected '89101234555', got '{result}'")
    result = sheets.normalize_phone('9101234555')
    if result != '89101234555':
        raise AssertionError(f"Expected '89101234555', got '{result}'")
    result = sheets.normalize_phone('89101234555')
    if result != '89101234555':
        raise AssertionError(f"Expected '89101234555', got '{result}'")
    result = sheets.normalize_phone('')
    if result != '':
        raise AssertionError(f"Expected '', got '{result}'")


def test_parse_init_data():
    s = 'user=123&auth_date=2025-09-16&hash=abc'
    d = tg.parse_init_data(s)
    if d['user'] != '123':
        raise AssertionError(f"Expected 'user' to be '123', got '{d['user']}'")
    if d['hash'] != 'abc':
        raise AssertionError(f"Expected 'hash' to be 'abc', got '{d['hash']}'")
