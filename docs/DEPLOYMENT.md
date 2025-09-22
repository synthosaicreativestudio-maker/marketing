# 🚀 Установка и развертывание MarketingBot

В этом документе описаны все шаги — от локальной установки для разработки до развертывания на сервере.

## 🖥️ Локальная установка

Этот способ подходит для быстрой проверки и разработки.

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
pip install -r requirements.txt
```

### 4. Настройка переменных окружения
```bash
# Копирование примера конфигурации
cp .env.example .env

# Редактирование .env файла
# Укажите как минимум TELEGRAM_TOKEN
nano .env
```

### 5. Запуск бота
```bash
# Простой запуск
python3 bot.py
```

## 🐳 Docker развертывание (для Production)

Docker — рекомендуемый способ для стабильной работы на сервере.

### 1. Настройка
```bash
# Убедитесь, что у вас настроен .env файл
cp .env.example .env
nano .env
```

### 2. Запуск с Docker Compose
```bash
# Запуск в фоновом режиме
docker-compose up -d

# Просмотр логов
docker-compose logs -f

# Остановка
docker-compose down
```

## ☁️ Развертывание в облаке (Пример для Google Cloud Run)

### 1. Сборка и отправка образа
```bash
gcloud builds submit --tag gcr.io/PROJECT_ID/marketingbot
```

### 2. Развертывание сервиса
```bash
gcloud run deploy marketingbot \
  --image gcr.io/PROJECT_ID/marketingbot \
  --platform managed \
  --region us-central1 \
  --set-env-vars TELEGRAM_TOKEN=your-token \
  --no-allow-unauthenticated
```

## 🚨 Устранение проблем

### Ошибка импорта `gspread` или `dotenv`:
Убедитесь, что вы активировали виртуальное окружение и выполнили `pip install -r requirements.txt`.

### Бот не отвечает:
1.  Проверьте правильность `TELEGRAM_TOKEN` в `.env`.
2.  Проверьте логи на наличие ошибок.
3.  Убедитесь, что сервер имеет доступ в интернет.

### Ошибки WebApp:
1.  Проверьте, что `WEBAPP_URL` в `.env` указан корректно и доступен.
