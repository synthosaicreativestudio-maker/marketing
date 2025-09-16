# Авторизационный поток (Mini App + Bot)

Коротко: пользователь открывает мини‑апп через кнопку "Авторизоваться", вводит Код партнёра и Телефон, мини‑апп шлёт POST /webapp/auth c initData и полями. Сервер валидирует initData (Telegram), нормализует телефон, ищет запись в Google Sheets по колонкам A (Код партнёра) и C (Телефон). При совпадении сервер записывает Telegram ID в колонку E, статус в D и дату в F и уведомляет пользователя.

Важные примечания:
- Храните сервисный аккаунт Google в секрете (GitHub Secret `GCP_SA_JSON` или Cloud Secret Manager).
- TELEGRAM_BOT_TOKEN — GitHub Secret `TELEGRAM_BOT_TOKEN`.
- Для локального теста используйте `ngrok` и polling или временный setWebhook на ngrok URL.

Файлы: `webapp/index.html`, `webapp/app.js`, `app/main.py` (FastAPI)
