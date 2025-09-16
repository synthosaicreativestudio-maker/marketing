# TESTING

Рекомендации по тестированию проекта:

- Unit tests: тестировать отдельные функции и модули.
- Integration tests: тестировать взаимодействие компонентов.
- E2E tests: симулировать рабочие сценарии.

Запуск тестов локально:

```bash
# пример: pytest
pytest
```

В CI запускать линтеры и тесты при каждом pull request.

Local helper scripts

There are three helper scripts in `scripts/` to help testing the WebApp auth flow locally:

- `scripts/generate_initdata.py` — generate a signed Telegram WebApp `initData` (HMAC using SHA256(bot_token)).
- `scripts/test_auth_via_bot.py` — convenience script that generates `initData` and POSTs to `http://127.0.0.1:8000/api/webapp/auth`.
- `scripts/send_webapp_button.py` — sends an inline keyboard with a Web App button to a chat (requires `BOT_TOKEN` env var).

Examples:

```
# generate initData
python scripts/generate_initdata.py --bot-token $BOT_TOKEN --user-id 123456

# run local test (will POST to local server)
export BOT_TOKEN=...
python scripts/test_auth_via_bot.py --user-id 123456 --partner-code 111098 --phone "+7 982 770-1055"

# send webapp button (after running ngrok and replacing URL)
python scripts/send_webapp_button.py --chat-id 123456 --url https://abcd-12.ngrok.io/webapp/index.html
```

Note: these helpers require `requests` installed in your virtualenv.

Ngrok & webhook notes

If you want Telegram to open your local Web App and forward `initData` automatically, expose your local server with ngrok:

```
.venv312/bin/uvicorn app.main:app --reload --port 8000
ngrok http 8000
```

Then set the webhook (optional) or send an inline Web App button that points to the ngrok URL. You can set webhook with:

```
export BOT_TOKEN=...
python scripts/setup_webhook.py --url https://abcd-12.ngrok.io/
```

Or send a button directly (no webhook needed) using `scripts/send_webapp_button.py`.

Restart script note

The `scripts/restart_bot.sh` script now checks for `TELEGRAM_BOT_TOKEN` (used by the app) and will warn if it's missing. Ensure your `.env` or environment uses that variable name.
