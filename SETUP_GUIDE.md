д# Руководство по установке и настройке

Это руководство поможет вам быстро развернуть и запустить проект "Marketing Bot" с нуля.

## Шаг 1: Подготовка

1.  **Клонируйте репозиторий:**
    ```bash
    git clone https://github.com/synthosaicreativestudio-maker/marketing.git
    cd marketing
    ```

2.  **Создайте и активируйте виртуальное окружение:**
    *   Это изолирует зависимости проекта от системных.
    ```bash
    # Для Windows
    python -m venv .venv
    .\.venv\Scripts\activate

    # Для macOS/Linux
    python3 -m venv .venv
    source .venv/bin/activate
    ```

## Шаг 2: Установка зависимостей

1.  **Создайте файл `requirements.txt`:**
    *   Этот файл нужен для `pip`, чтобы установить все необходимые библиотеки одной командой.

2.  **Установите зависимости:**
    ```bash
    pip install python-telegram-bot python-dotenv gspread oauth2client
    ```
    *После установки рекомендуется создать `requirements.txt` командой:*
    ```bash
    pip freeze > requirements.txt
    ```

## Шаг 3: Настройка конфигурации

1.  **Создайте файл `.env`:**
    *   В корне проекта создайте файл с именем `.env`.

2.  **Заполните `.env`:**
    *   Скопируйте в него следующие переменные и подставьте свои значения:
    ```env
    # Токен вашего Telegram-бота (получается у @BotFather)
    TELEGRAM_TOKEN="ВАШ_TELEGRAM_ТОКЕН"

    # Ваш Telegram ID для отправки админских уведомлений (можно узнать у @userinfobot)
    ADMIN_TELEGRAM_ID="ВАШ_TELEGRAM_ID"

    # Ключ от OpenAI (если планируется использовать)
    OPENAI_API_KEY="sk-..."
    
    # ID ассистента OpenAI (если планируется использовать)
    OPENAI_ASSISTANT_ID="asst_..."

    # Полный URL вашей Google Таблицы для авторизации
    SHEET_URL="https://docs.google.com/spreadsheets/d/..."

    # Полный URL вашей Google Таблицы для заявок
    TICKETS_SHEET_URL="https://docs.google.com/spreadsheets/d/..."

    # URL развернутого Mini App (после настройки GitHub Pages)
    WEB_APP_URL="https://your-github-username.github.io/marketing/"
    
    # URL для меню в Mini App (если будет использоваться)
    WEB_APP_MENU_URL="https://your-github-username.github.io/marketing/mini_app.html"
    
    # Токен GitHub для доступа к API (если нужен)
    GITHUB_PAT="github_pat_..."
    ```

3.  **Настройте `credentials.json`:**
    *   Поместите файл `credentials.json`, скачанный из Google Cloud Console, в корень проекта.
    *   **Важно:** Убедитесь, что у сервисного аккаунта есть права "Редактора" для ваших Google Таблиц. Для этого откройте доступ к таблицам для `client_email` из вашего `credentials.json`.

## Шаг 4: Первый запуск

После выполнения всех шагов вы готовы к запуску.

1.  **Убедитесь, что виртуальное окружение активировано.**
2.  **Выполните команду в терминале:**
    ```bash
    python bot.py
    ```

Если все настроено правильно, в консоли появятся логи об успешной инициализации и запуске бота.