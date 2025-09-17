Google Sheets: настройка сервисного аккаунта и переменных окружения

1) Создать проект в GCP и включить Google Sheets API.

2) Создать сервисный аккаунт (IAM -> Service Accounts) с ролью Editor (или более узкой — только доступ к Sheets). Сгенерировать JSON ключ и сохранить локально.

3) Открыть Google Sheet и поделиться (Share) с email сервисного аккаунта (пример: my-sa@project.iam.gserviceaccount.com) с правом Editor.

4) Два варианта передачи credentials в приложение:
  - Поместить JSON в переменную окружения `GCP_SA_JSON` (содержимое файла JSON как строка).
  - Или положить файл на диск и указать путь в `GCP_SA_FILE`.

5) Указать `SHEET_ID` в окружении: это часть URL таблицы (https://docs.google.com/spreadsheets/d/<SHEET_ID>/edit).
   Опционально указать `SHEET_NAME` если требуется не первый лист.

6) Примеры (macOS zsh):

export GCP_SA_FILE="$HOME/secrets/my-sa.json"
export SHEET_ID="1AbCdEfGhIJkLmNoPqRsTuVwXyZ"

или

export GCP_SA_JSON='{"type":...}'

7) Локальная проверка:

- Запустить сервер: .venv312/bin/uvicorn app.main:app --reload
- Выполнить POST /api/webapp/auth с реальным partner_code и телефоном, который есть в таблице.

8) Безопасность:

- Не храните JSON в репозитории. Используйте секреты CI для хранения `GCP_SA_JSON` и `SHEET_ID`.
