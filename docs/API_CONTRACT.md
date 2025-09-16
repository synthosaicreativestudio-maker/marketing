# API contract: Mini App -> Backend (/webapp/auth)

Кратко: Mini App (Telegram Web App) отправляет POST /webapp/auth с полями { initData, partner_code, partner_phone }.

1) Endpoint

- URL: POST /webapp/auth
- Content-Type: application/json

2) Request body

{
  "initData": "<string>",    // Telegram Web App initData (строка из window.Telegram.WebApp.initData)
  "partner_code": "<digits>", // только цифры, обязательное
  "partner_phone": "<string>"  // что ввёл пользователь; может содержать +, пробелы, скобки
}

3) Validation rules

- `initData` обязателен. Сервер должен проверить подпись initData по алгоритму Telegram (использовать bot token). Для краткости: проверить HMAC-SHA256 по полю `hash` как в официальной документации и сравнить с calculated signature.
- `partner_code` — строка только из цифр. Длина и правила зависят от партнёров (по умолчанию 1..20).
- `partner_phone` — нормализуется сервером в формат без пробелов и символов, заменяя +7 на 8, добавляя 8 если номер из 10 цифр без лидера.

4) Phone normalization algorithm (server-side)

- Удалить все символы кроме цифр.
- Если номер начинается с `8` и длина 11 — OK.
- Если номер начинается с `7` и длина 11 — заменить 7 на 8.
- Если длина 10 — добавить ведущую `8`.
- В остальных случаях — ошибка 400 с message: "invalid_phone".

5) Google Sheets mapping (read/update)

- Таблица ожидается со столбцами (A..F) где:
  - A: partner_code
  - B: (другие данные)
  - C: partner_phone (в той же нормализации как на шаге 4)
  - D: Status (string) — будет записан "authorized" или "rejected" и/или текст ошибки
  - E: telegram_id (число)
  - F: auth_date (ISO 8601 timestamp)

- Логика поиска: найти строку, где A == partner_code AND C == partner_phone (после нормализации).
- Если совпадение найдено — обновить E (telegram_id), D (status) и F (auth_date). Если не найдено — вернуть 404 с message: "not_found".

6) Response formats

- Success (200):

{
  "ok": true,
  "message": "authorized",
  "user": {
    "telegram_id": 123456789,
    "partner_code": "111098",
    "partner_phone": "89101234555"
  }
}

- Client error (400):

{
  "ok": false,
  "error": "invalid_initdata|invalid_phone|invalid_partner_code",
  "message": "human friendly message"
}

- Not found (404):

{
  "ok": false,
  "error": "not_found",
  "message": "Partner code + phone pair not found"
}

- Server error (500):

{
  "ok": false,
  "error": "server_error",
  "message": "Details omitted"
}

7) Side effects

- При успешной валидации и записи в Sheets сервер должен также отправить сообщение пользователю через Bot API (отправить confirmation message в чат с telegram_id если известен) и логировать операцию.

8) Security notes

- Всегда валидировать `initData` и сравнивать время (field `auth_date` из initData) чтобы избежать replay-атак.
- Использовать сервисный аккаунт Google с минимальными правами: доступ только к конкретной таблице.
- Хранить GCP ключи в GitHub Secrets / env vars, не в репозитории.

9) Errors and status codes summary

- 200 OK — авторизация успешна и запись в таблице выполнена.
- 400 Bad Request — проблема в данных запроса (invalid_initdata, invalid_phone, invalid_partner_code).
- 404 Not Found — пара partner_code+phone не найдена.
- 401 Unauthorized — если проверка initData не пройдена (опция: 400 тоже допустим).
- 500 Internal Server Error — неожиданные ошибки.

10) Example request

POST /webapp/auth
Content-Type: application/json

{
  "initData": "user=...&auth_date=...&hash=...",
  "partner_code": "111098",
  "partner_phone": "+7 (910) 123-45-55"
}

Example success response (200):

{
  "ok": true,
  "message": "authorized",
  "user": { "telegram_id": 123456789, "partner_code": "111098", "partner_phone": "89101234555" }
}
