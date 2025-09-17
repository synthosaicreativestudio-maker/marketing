# 🚀 Установка MarketingBot

## 📦 Быстрая установка

### 1. Клонирование репозитория
```bash
git clone <repository-url>
cd marketingbot
```

### 2. Создание виртуального окружения
```bash
# Создание окружения
python3 -m venv .venv

# Активация (Linux/Mac)
source .venv/bin/activate

# Активация (Windows)
.venv\Scripts\activate
```

### 3. Установка зависимостей
```bash
# Установка через pip
pip install requests python-dotenv gspread google-auth

# Или через pyproject.toml
pip install -e .
```

### 4. Настройка переменных окружения
```bash
# Копирование примера конфигурации
cp .env.example .env

# Редактирование .env файла
nano .env
```

### 5. Запуск бота
```bash
# Простой запуск
python3 bot.py

# С виртуальным окружением
.venv/bin/python bot.py
```

## ⚙️ Настройка переменных окружения

### Обязательные параметры:
```env
# Токен бота от @BotFather
TELEGRAM_BOT_TOKEN=your-bot-token-here

# URL веб-приложения
WEBAPP_URL=https://your-domain.com/webapp
```

### Опциональные (для Google Sheets):
```env
# Google Sheets интеграция
SHEET_ID=your-google-sheets-id
SHEET_NAME=Sheet1
GCP_SA_JSON='{"type":"service_account",...}'
# Или
GCP_SA_FILE=path/to/service-account.json
```

## 📝 Проверка установки

### Проверка синтаксиса:
```bash
python3 -m py_compile bot.py
python3 -m py_compile sheets.py
```

### Проверка импортов:
```bash
python3 -c "import bot; print('✅ bot.py импортируется корректно')"
python3 -c "import sheets; print('✅ sheets.py импортируется корректно')"
```

### Проверка конфигурации:
```bash
# Проверка загрузки .env
python3 -c "from dotenv import load_dotenv; import os; load_dotenv(); print('✅ .env загружен' if os.getenv('TELEGRAM_BOT_TOKEN') else '❌ Нет TELEGRAM_BOT_TOKEN')"
```

## 🐛 Решение проблем

### Ошибка импорта gspread:
```bash
pip install gspread google-auth
```

### Ошибка импорта dotenv:
```bash
pip install python-dotenv
```

### Ошибка с токеном:
1. Проверьте .env файл
2. Убедитесь, что токен корректный
3. Перезапустите бота

docker-compose up -d
docker-compose logs -f marketingbot
docker-compose down
docker build -t marketingbot .
docker run -d \
docker logs -f marketingbot
## Container usage (optional)

Using Docker is optional. The recommended, simpler path is to run the bot without Docker as described in `README.md` (Run without Docker). If your environment requires containers (Cloud Run, Kubernetes, etc.), consult the README or keep local copy of Docker commands as legacy references.

## 🔧 Разработка

### Установка инструментов разработки:
```bash
pip install ruff mypy black isort
```

### Проверка качества кода:
```bash
# Проверка стиля
ruff check .

# Проверка типов
mypy . --ignore-missing-imports

# Форматирование
black .
```
