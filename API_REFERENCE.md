# Справочник по внешним API

Этот документ централизует информацию о внешних сервисах (API), от которых зависит проект.

## 1. Telegram Bot API

*   **Назначение:** Основной интерфейс для взаимодействия с пользователями через Telegram.
*   **Библиотека:** `python-telegram-bot`
*   **Используемые методы (неявно через библиотеку):**
    *   `run_polling()`: Получение обновлений от Telegram.
    *   `sendMessage`: Отправка текстовых сообщений.
    *   `InlineKeyboardMarkup`: Создание inline-клавиатур.
    *   `WebAppInfo`: Конфигурация для запуска Mini App.
*   **Ключевой объект:** `Update` - содержит всю информацию о событии (сообщение, команда, данные из Mini App).
*   **Документация:** [https://core.telegram.org/bots/api](https://core.telegram.org/bots/api)

## 2. Google Sheets API

*   **Назначение:** Используется как база данных для хранения информации о пользователях, их статусах авторизации и заявках.
*   **Библиотека:** `gspread` (обертка над Google Sheets API)
*   **Права доступа (Scopes):**
    *   `https://spreadsheets.google.com/feeds`: Полный доступ к таблицам (старая версия, но gspread все еще ее требует).
    *   `https://www.googleapis.com/auth/drive`: Доступ к файлам на Google Drive (необходим для поиска и открытия таблиц по имени или URL).
*   **Используемые методы (через `gspread`):**
    *   `gspread.authorize()`: Аутентификация с помощью `credentials.json`.
    *   `client.open_by_url()`: Открытие таблицы по ее полному URL.
    *   `sheet.get_all_records()`: Получение всех данных с листа в виде списка словарей.
    *   `sheet.find()`: Поиск ячейки по значению.
    *   `sheet.update_cell()`: Обновление значения в конкретной ячейке.
*   **Документация:** [https://docs.gspread.org/](https://docs.gspread.org/)

## 3. OpenAI API

*   **Назначение:** Планируется для использования в `v2.0.0` для реализации интеллектуальных функций (ассистент, обработка текста).
*   **Статус:** Не используется в текущей версии (`v0.1.0`).
*   **Переменные в `.env`:** `OPENAI_API_KEY`, `OPENAI_ASSISTANT_ID`.
*   **Документация:** [https://platform.openai.com/docs/api-reference](https://platform.openai.com/docs/api-reference)