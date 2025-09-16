import logging
import os
from contextlib import suppress
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from pythonjsonlogger import jsonlogger

from . import bot_helper, sheets
from . import telegram as tg

# configure structured logging
handler = logging.StreamHandler()
formatter = jsonlogger.JsonFormatter('%(asctime)s %(levelname)s %(name)s %(message)s')
handler.setFormatter(formatter)
root = logging.getLogger()
root.setLevel(logging.INFO)
root.addHandler(handler)

# create FastAPI app early so decorators can reference it
app = FastAPI()

try:
    from prometheus_client import CONTENT_TYPE_LATEST, Counter, generate_latest
    AUTH_ATTEMPTS = Counter('auth_attempts_total', 'Total auth attempts')
    AUTH_SUCCESS = Counter('auth_success_total', 'Total successful auths')
    AUTH_FAILURE = Counter('auth_failure_total', 'Total failed auths')

    @app.get('/metrics')
    def metrics_endpoint():
        # return raw prometheus metrics text with proper content type
        return generate_latest(), 200, {'Content-Type': CONTENT_TYPE_LATEST}
except Exception:
    # prometheus-client not installed or import failed; provide no-op counters
    # and minimal endpoint
    class _NoopCounter:
        def inc(self, *a, **k):
            return None

    AUTH_ATTEMPTS = _NoopCounter()
    AUTH_SUCCESS = _NoopCounter()
    AUTH_FAILURE = _NoopCounter()

    # metrics endpoint not available when prometheus_client is missing

# Serve static mini-app files under /webapp
app.mount(
    '/webapp',
    StaticFiles(directory=Path(__file__).parent.parent / 'webapp'),
    name='webapp'
)


class AuthRequest(BaseModel):
    init_data: str
    partner_code: str
    partner_phone: str


@app.get("/")
async def root():
    """Redirect to webapp."""
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/webapp/index.html")


@app.get("/healthz")
async def healthz():
    return {"status": "ok"}


@app.post("/api/webapp/auth")
async def webapp_auth(req: AuthRequest, request: Request):
    # Metrics: count attempt
    with suppress(Exception):
        AUTH_ATTEMPTS.inc()

    # Validate partner_code
    partner_code = (req.partner_code or '').strip()
    if not partner_code.isdigit():
        AUTH_FAILURE.inc()
        raise HTTPException(status_code=400, detail="partner_code must be numeric")

    # Validate presence of init_data
    init_data = (req.init_data or '').strip()
    if not init_data:
        AUTH_FAILURE.inc()
        raise HTTPException(status_code=401, detail="missing init_data")

    # Validate init_data signature if bot token present
    bot_token = os.environ.get('TELEGRAM_BOT_TOKEN')
    if bot_token and not tg.validate_init_data(init_data, bot_token):
        AUTH_FAILURE.inc()
        raise HTTPException(status_code=401, detail="invalid_initdata")

    # Normalize phone using sheets helper
    phone_norm = sheets.normalize_phone((req.partner_phone or '').strip())

    try:
        row = sheets.find_row_by_partner_and_phone(partner_code, phone_norm)
        if not row:
            # fallback PoC behavior for dev if sheets not configured isn't
            # applicable here
            AUTH_FAILURE.inc()
            raise HTTPException(status_code=404, detail="not_found")

        # extract telegram id from init_data; fallback to 0
        telegram_id = tg.extract_telegram_id(init_data) or 0

        # Update sheet (may raise)
        sheets.update_row_with_auth(row, telegram_id, status='authorized')

        # Send confirmation (non-blocking): log failures but don't fail the request
        try:
            bot_helper.send_message_to(telegram_id, 'Вы авторизованы', background=True)
        except Exception:
            logging.exception('Failed to send confirmation message to %s', telegram_id)

        with suppress(Exception):
            AUTH_SUCCESS.inc()

        return {
            "ok": True, "message": "authorized",
            "row": row, "telegram_id": telegram_id
        }

    except sheets.SheetsNotConfiguredError:
        # Development fallback: simple deterministic PoC
        if partner_code == '111098' and phone_norm.endswith('1055'):
            with suppress(Exception):
                AUTH_SUCCESS.inc()
            return {"ok": True, "message": "authorized (poс)"}
        raise HTTPException(status_code=404, detail="sheet_not_configured") from None
    except HTTPException:
        # re-raise explicit HTTP errors
        raise
    except Exception as e:
        with suppress(Exception):
            AUTH_FAILURE.inc()
        logging.exception('Unhandled error in webapp_auth')
        raise HTTPException(status_code=500, detail=str(e)) from e
