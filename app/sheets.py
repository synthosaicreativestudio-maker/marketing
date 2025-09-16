import json
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# optional prometheus metrics
try:
    from prometheus_client import Counter
    SHEETS_UPDATES = Counter('sheets_updates_total', 'Total sheet update attempts')
    SHEETS_UPDATE_FAILURES = Counter(
        'sheets_update_failures_total', 'Total failed sheet updates'
    )
except Exception:
    class _Noop:
        def inc(self, *a, **k):
            return None

    SHEETS_UPDATES = _Noop()
    SHEETS_UPDATE_FAILURES = _Noop()


class SheetsNotConfiguredError(Exception):
    pass


def _load_service_account():
    # Prefer JSON content in env, fallback to file path
    sa_json = os.environ.get('GCP_SA_JSON')
    sa_file = os.environ.get('GCP_SA_FILE')
    if sa_json:
        try:
            return json.loads(sa_json)
        except Exception as e:
            raise ValueError('Invalid GCP_SA_JSON: ' + str(e)) from e
    if sa_file and Path(sa_file).exists():
        with Path(sa_file).open(encoding='utf-8') as f:
            return json.load(f)
    raise SheetsNotConfiguredError(
        'Service account JSON not provided (GCP_SA_JSON or GCP_SA_FILE)'
    )


def _get_client_and_sheet(retries: int = 3, backoff: float = 1.0):
    try:
        import gspread
    except Exception as e:
        raise RuntimeError('gspread is required: ' + str(e)) from e

    sa_dict = _load_service_account()

    attempt = 0
    sheet_id = os.environ.get('SHEET_ID')
    if not sheet_id:
        raise SheetsNotConfiguredError('SHEET_ID env var is required')

    while True:
        attempt += 1
        try:
            creds = gspread.service_account_from_dict(sa_dict)
            sh = creds.open_by_key(sheet_id)
            sheet_name = os.environ.get('SHEET_NAME') or sh.sheet1.title
            ws = sh.worksheet(sheet_name)
            return ws
        except Exception as e:
            logger.warning('Sheets access attempt %s failed: %s', attempt, e)
            if attempt >= retries:
                logger.exception('Sheets access failed after %s attempts', attempt)
                raise
            sleep = backoff * (2 ** (attempt - 1))
            time.sleep(sleep)


def normalize_phone(phone: str) -> str:
    digits = ''.join(ch for ch in (phone or '') if ch.isdigit())
    if len(digits) == 10:
        return '8' + digits
    if len(digits) == 11 and digits.startswith('7'):
        return '8' + digits[1:]
    if len(digits) == 11 and digits.startswith('8'):
        return digits
    return digits


def find_row_by_partner_and_phone(
    partner_code: str, phone_normalized: str
) -> Optional[int]:
    """Return the 1-based row index if found, else None."""
    ws = _get_client_and_sheet()
    all_values = ws.get_all_values()
    # assume header in first row
    for idx, row in enumerate(all_values[1:], start=2):
        a = (row[0].strip() if len(row) >= 1 else '')
        c = (row[2].strip() if len(row) >= 3 else '')
        if a == partner_code and normalize_phone(c) == phone_normalized:
            return idx
    return None


def update_row_with_auth(
    row: int, telegram_id: int, status: str = 'authorized',
    retries: int = 3, backoff: float = 1.0
) -> None:
    ws = _get_client_and_sheet()
    now = datetime.now(timezone.utc).isoformat()
    attempt = 0
    SHEETS_UPDATES.inc()
    while True:
        attempt += 1
        try:
            # D = col 4, E = col5, F = col6
            ws.update_cell(row, 5, str(telegram_id) if telegram_id else '')
            ws.update_cell(row, 4, status)
            ws.update_cell(row, 6, now)
            logger.info(
                'Updated row %s: status=%s telegram_id=%s', row, status, telegram_id
            )
            return
        except Exception as e:
            logger.warning('Update attempt %s failed for row %s: %s', attempt, row, e)
            if attempt >= retries:
                logger.exception(
                    'Failed to update row %s after %s attempts', row, attempt
                )
                SHEETS_UPDATE_FAILURES.inc()
                raise
            sleep = backoff * (2 ** (attempt - 1))
            time.sleep(sleep)
