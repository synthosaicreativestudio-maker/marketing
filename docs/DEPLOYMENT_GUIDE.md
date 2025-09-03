# 🚀 Руководство по развертыванию Marketing Bot

## 📋 Предварительные требования

### **Системные требования**
- **ОС**: macOS 10.15+, Ubuntu 18.04+, CentOS 7+
- **Python**: 3.8+
- **Память**: минимум 512MB RAM
- **Диск**: минимум 1GB свободного места
- **Сеть**: доступ к интернету

### **Внешние сервисы**
- **Telegram Bot API** - токен бота
- **Google Sheets API** - доступ к таблицам
- **OpenAI API** - ключ для AI функций

## 🔧 Установка

### **1. Клонирование репозитория**
```bash
git clone <repository_url>
cd @marketing
```

### **2. Установка зависимостей**
```bash
pip install -r requirements.txt
```

### **3. Настройка переменных окружения**
Создайте файл `.env`:
```bash
# Telegram Bot
TELEGRAM_TOKEN=your_bot_token_here
ADMIN_TELEGRAM_ID=123456789,987654321

# Google Sheets
SHEET_URL=https://docs.google.com/spreadsheets/d/your_sheet_id
TICKETS_SHEET_URL=https://docs.google.com/spreadsheets/d/your_tickets_sheet_id
PROMOTIONS_SHEET_URL=https://docs.google.com/spreadsheets/d/your_promotions_sheet_id

# OpenAI
OPENAI_API_KEY=sk-your_openai_key_here
OPENAI_ASSISTANT_ID=asst-your_assistant_id_here

# Optional
GOOGLE_CREDENTIALS_PATH=credentials.json
LOG_FILE=bot.log
```

### **4. Настройка Google Sheets API**
1. Создайте проект в [Google Cloud Console](https://console.cloud.google.com/)
2. Включите Google Sheets API
3. Создайте Service Account
4. Скачайте JSON ключ как `credentials.json`
5. Предоставьте доступ к таблицам для Service Account

### **5. Настройка OpenAI**
1. Получите API ключ в [OpenAI Console](https://platform.openai.com/)
2. Создайте Assistant в OpenAI Playground
3. Скопируйте Assistant ID

## 🏃‍♂️ Запуск

### **Разработка (Development)**
```bash
# Простой запуск
python3 bot.py

# С логированием
python3 bot.py > bot.log 2>&1

# В фоне
nohup python3 bot.py > bot.log 2>&1 &
```

### **Production (macOS)**
```bash
# Использование launchd
./run_single_bot.sh

# Или через manage_bot.py
python3 manage_bot.py start
```

### **Production (Linux)**
```bash
# Использование systemd
sudo cp marketing-bot.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable marketing-bot
sudo systemctl start marketing-bot
```

## 🔧 Управление

### **Команды управления**
```bash
# Статус
python3 manage_bot.py status

# Запуск
python3 manage_bot.py start

# Остановка
python3 manage_bot.py stop

# Перезапуск
python3 manage_bot.py restart

# Логи
python3 manage_bot.py logs -f

# Проверка здоровья
python3 manage_bot.py health
```

### **Системные команды (macOS)**
```bash
# Запуск через launchd
launchctl load ~/Library/LaunchAgents/com.marketing.telegram-bot.plist
launchctl start com.marketing.telegram-bot

# Остановка
launchctl stop com.marketing.telegram-bot
launchctl unload ~/Library/LaunchAgents/com.marketing.telegram-bot.plist
```

### **Системные команды (Linux)**
```bash
# Запуск
sudo systemctl start marketing-bot

# Остановка
sudo systemctl stop marketing-bot

# Статус
sudo systemctl status marketing-bot

# Логи
sudo journalctl -u marketing-bot -f
```

## 📊 Мониторинг

### **Логи**
```bash
# Просмотр логов
tail -f bot.log

# Поиск ошибок
grep -i error bot.log

# Статистика
grep -c "INFO\|WARNING\|ERROR" bot.log
```

### **Процессы**
```bash
# Поиск процессов бота
ps aux | grep bot.py

# Мониторинг ресурсов
top -p $(pgrep -f bot.py)
```

### **Метрики производительности**
Бот автоматически собирает метрики:
- Время выполнения операций
- Процент успешных операций
- Статистика по внешним API
- Использование памяти и CPU

## 🔒 Безопасность

### **Переменные окружения**
- Никогда не коммитьте `.env` файлы
- Используйте сильные пароли для API ключей
- Регулярно ротируйте ключи

### **Доступ к файлам**
```bash
# Правильные права доступа
chmod 600 .env
chmod 600 credentials.json
chmod 755 *.sh
```

### **Firewall**
```bash
# Разрешить только необходимые порты
# Бот не открывает входящие порты, только исходящие HTTPS
```

## 🚨 Устранение неполадок

### **Частые проблемы**

#### **1. Бот не запускается**
```bash
# Проверьте токен
echo $TELEGRAM_TOKEN

# Проверьте зависимости
pip list | grep -E "(telegram|openai|gspread)"

# Проверьте логи
cat bot.log | tail -20
```

#### **2. Ошибки Google Sheets**
```bash
# Проверьте credentials.json
python3 -c "import json; print(json.load(open('credentials.json')))"

# Проверьте доступ к таблицам
# Убедитесь что Service Account имеет доступ
```

#### **3. Ошибки OpenAI**
```bash
# Проверьте API ключ
python3 -c "import openai; print(openai.api_key)"

# Проверьте Assistant ID
echo $OPENAI_ASSISTANT_ID
```

#### **4. Проблемы с авторизацией**
```bash
# Очистите кэш
rm -f auth_cache.json
rm -f mcp_context_data.json

# Перезапустите бота
python3 manage_bot.py restart
```

### **Диагностика**
```bash
# Полная диагностика
python3 advanced_diagnostics.py

# Проверка конфигурации
python3 -c "from config import validate_config; print(validate_config())"

# Тест подключений
python3 -c "from sheets_client import GoogleSheetsClient; print('Sheets OK')"
python3 -c "from openai_client import openai_client; print(openai_client.is_available())"
```

## 📈 Масштабирование

### **Для большого количества пользователей**
1. **Увеличьте лимиты в `config.py`**:
   ```python
   SCALING_CONFIG = {
       'MAX_CONCURRENT_REQUESTS': 20,  # Увеличить
       'MAX_CACHE_SIZE': 50000,        # Увеличить
       'MONITORING_INTERVAL': 30,      # Уменьшить
   }
   ```

2. **Настройте мониторинг**:
   - Добавьте Prometheus метрики
   - Настройте Grafana дашборды
   - Добавьте алерты

3. **Оптимизируйте базу данных**:
   - Используйте кэширование
   - Оптимизируйте запросы к Google Sheets
   - Рассмотрите миграцию на PostgreSQL

### **Высокая доступность**
1. **Настройте резервное копирование**:
   ```bash
   # Backup скрипт
   tar -czf backup-$(date +%Y%m%d).tar.gz . --exclude='*.log'
   ```

2. **Настройте мониторинг**:
   - Health checks
   - Автоматический перезапуск
   - Уведомления об ошибках

## 🔄 Обновления

### **Обновление кода**
```bash
# Создайте backup
cp -r . ../backup-$(date +%Y%m%d)

# Обновите код
git pull origin main

# Установите новые зависимости
pip install -r requirements.txt

# Перезапустите
python3 manage_bot.py restart
```

### **Откат изменений**
```bash
# Откат к предыдущей версии
git checkout rollback-point-YYYYMMDD-HHMMSS

# Или к конкретному коммиту
git checkout <commit_hash>

# Перезапустите
python3 manage_bot.py restart
```

## 📞 Поддержка

### **Логи для поддержки**
```bash
# Соберите информацию для поддержки
{
    echo "=== System Info ==="
    uname -a
    python3 --version
    echo "=== Bot Status ==="
    python3 manage_bot.py status
    echo "=== Recent Logs ==="
    tail -50 bot.log
    echo "=== Configuration ==="
    python3 -c "from config import validate_config; print(validate_config())"
} > support_info.txt
```

### **Контакты**
- **Техническая поддержка**: [ваш email]
- **Документация**: `docs/` папка
- **Issues**: GitHub Issues

---

**Последнее обновление**: 2025-01-03 08:57
**Версия руководства**: 1.0
**Статус**: Актуально
