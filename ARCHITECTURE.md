? или роад мэ# Архитектура проекта "Marketing Bot"

Этот документ описывает архитектуру и потоки данных в проекте.

## 1. Обзор компонентов

Система состоит из следующих ключевых компонентов:

*   **Telegram Bot API:** Внешний сервис, через который пользователи взаимодействуют с ботом.
*   **Бот (`bot.py`):** Основное приложение на Python, которое получает обновления от Telegram.
*   **Обработчики (`handlers.py`):** Модуль, который маршрутизирует команды и данные от пользователя к соответствующей бизнес-логике.
*   **Сервис авторизации (`auth_service.py`):** Модуль, инкапсулирующий логику проверки учетных данных пользователя.
*   **Сервис Google Sheets (`google_sheets_service.py`):** Низкоуровневая обертка для работы с Google Sheets API.
*   **Mini App (`index.html`):** Фронтенд-приложение, работающее внутри Telegram, для сбора данных от пользователя.
*   **Google Sheets:** Внешняя база данных, где хранятся данные пользователей.

## 2. Схема взаимодействия

```mermaid
graph TD
    A[Пользователь] -- /start --> B(Telegram Bot API);
    B -- Update --> C[bot.py: Application];
    C -- Command --> D[handlers.py];
    D -- Проверка статуса --> E[auth_service.py];
    E -- get_user_auth_status --> F[google_sheets_service.py];
    F -- Чтение данных --> G[(Google Sheet)];
    
    subgraph "Если не авторизован"
        D -- Отправка кнопки --> B;
        A -- Нажатие кнопки --> H{Mini App: index.html};
        H -- Ввод данных --> I(JS: tg.sendData());
        I -- WebAppData --> B;
        B -- Update --> C;
        C -- WebAppData --> D;
        D -- find_and_update_user --> E;
        E -- find_and_update_user --> F;
        F -- Запись данных --> G;
    end

    subgraph "Если авторизован"
        D -- Показ меню --> B;
    end
```

## 3. Поток данных (Data Flow) при авторизации

1.  **Запрос:** Пользователь отправляет команду `/start`.
2.  **Маршрутизация:** `bot.py` получает `Update` и передает его в `start_command_handler` в `handlers.py`.
3.  **Проверка:** `start_command_handler` вызывает `auth_service.get_user_auth_status()`.
4.  **Доступ к данным:** `auth_service` через `google_sheets_service` обращается к Google Sheet для проверки статуса пользователя.
5.  **Ответ:**
    *   **Если пользователь не авторизован:** `handlers.py` формирует `InlineKeyboardButton` с `web_app` информацией и отправляет ее пользователю.
    *   **Если пользователь авторизован:** `handlers.py` отправляет обычное приветствие (в будущем — главное меню).
6.  **Ввод в Mini App:** Пользователь нажимает кнопку, открывает `index.html` и вводит свои данные.
7.  **Отправка данных:** JavaScript в `index.html` формирует JSON с данными и отправляет его через `window.Telegram.WebApp.sendData()`.
8.  **Получение данных:** `bot.py` получает `Update` с `web_app_data` и передает его в `web_app_data_handler` в `handlers.py`.
9.  **Финальная проверка:** `web_app_data_handler` вызывает `auth_service.find_and_update_user()`.
10. **Обновление БД:** `auth_service` через `google_sheets_service` находит нужную строку в Google Sheet и обновляет поля "Статус", "Telegram ID" и "Дата".
11. **Фидбэк:** `handlers.py` отправляет пользователю сообщение об успешной или неуспешной авторизации.