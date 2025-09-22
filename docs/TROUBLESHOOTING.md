# 🔧 Устранение неполадок MarketingBot

## 🚨 Частые проблемы и решения

### 1. Бот не отвечает на команды

**Симптомы:**
- Бот не реагирует на `/start`
- Нет ответа от бота в Telegram

**Возможные причины и решения:**

#### Проблема с токеном:
```bash
# Проверка токена
python3 -c "from dotenv import load_dotenv; import os; load_dotenv(); print('Token:', 'OK' if os.getenv('TELEGRAM_TOKEN') else 'MISSING')"

# Проверка валидности токена
curl "https://api.telegram.org/bot<YOUR_TOKEN>/getMe"
```

#### Проблема с сетью:
```bash
# Проверка подключения к Telegram API
curl -I https://api.telegram.org

# Проверка DNS
nslookup api.telegram.org
```

#### Проблема с процессом:
```bash
# Проверка запущенных процессов
pgrep -f "python.*bot.py"

# Перезапуск бота
pkill -f "python.*bot.py"
python3 bot.py
```

### 2. WebApp не открывается

**Симптомы:**
- Кнопка "Авторизоваться" не работает
- Ошибка при открытии веб-приложения

**Решения:**

#### Проверка WEBAPP_URL:
```bash
# Проверка переменной
echo $WEBAPP_URL

# Проверка доступности URL
curl -I $WEBAPP_URL
```

#### Проверка файлов WebApp:
```bash
# Проверка наличия файлов
ls -la
cat index.html | head -10
```

#### Проблемы с HTTPS:
- WebApp требует HTTPS для работы в Telegram
- Используйте ngrok для локального тестирования:
```bash
ngrok http 8080
# Используйте HTTPS URL в WEBAPP_URL
```

### 3. Ошибки авторизации

**Симптомы:**
- "Партнёр не найден в базе"
- Ошибки при обработке данных

**Решения:**

#### Проблемы с Google Sheets:
```bash
# Проверка service account
python3 -c "import json; print(json.loads(open('.env').read().split('GCP_SA_JSON=')[1].split('\n')[0])['client_email'])"

# Проверка доступа к таблице
python3 -c "from sheets import _get_client_and_sheet; client, sheet = _get_client_and_sheet(); print('Sheets OK')"
```

#### Fallback авторизация:
- Если Google Sheets не настроены, используется простая проверка
- Тестовые данные: код `111098`, телефон с `1055`

### 4. Container notes (optional)

Containerization (Docker) was supported previously but is optional in the simplified project layout. The recommended workflow is to run the bot without Docker; see `README.md` -> "Run without Docker" for step-by-step instructions.

If you still rely on containers for your environment (legacy), keep your local Docker commands and troubleshooting steps. Container troubleshooting is considered out-of-scope for the simplified guide, but feel free to ask and I will assist with specific issues.

### 5. Проблемы с зависимостями

**Симптомы:**
- ImportError при запуске
- Ошибки установки пакетов

**Решения:**

#### Переустановка зависимостей:
```bash
# Очистка виртуального окружения
rm -rf .venv
python3 -m venv .venv
source .venv/bin/activate

# Установка зависимостей
pip install requests python-dotenv gspread google-auth
```

#### Проблемы с Python версией:
```bash
# Проверка версии Python
python3 --version

# Использование правильной версии
python3.12 -m venv .venv
```

## 🔍 Диагностические команды

### Проверка системы:
```bash
# Общая проверка
python3 -c "
import sys, os
from dotenv import load_dotenv
load_dotenv()

print(f'Python: {sys.version}')
print(f'Token: {\"OK\" if os.getenv(\"TELEGRAM_TOKEN\") else \"MISSING\"}')
print(f'WebApp URL: {os.getenv(\"WEBAPP_URL\", \"NOT SET\")}')

try:
    import requests, gspread
    print('Dependencies: OK')
except ImportError as e:
    print(f'Dependencies: ERROR - {e}')
"
```

### Проверка бота:
```bash
# Тест импортов
python3 -c "import bot, sheets; print('Imports: OK')"

# Тест запуска (5 секунд)
timeout 5 python3 bot.py || echo "Bot startup: OK"
```

### Проверка Docker:
```bash
# Проверка образа
docker run --rm --env-file .env marketingbot python3 -c "print('Docker: OK')"

# Проверка логов
docker-compose logs --tail=50 marketingbot
```

## 📊 Мониторинг и логи

### Просмотр логов:
```bash
# Локальные логи
python3 bot.py 2>&1 | tee bot.log

# Docker логи
docker-compose logs -f marketingbot

# Системные логи
journalctl -u marketingbot -f
```

### Мониторинг ресурсов:
```bash
# Использование CPU/памяти
top -p $(pgrep -f "python.*bot.py")

# Docker статистика
docker stats marketingbot

# Дисковое пространство
df -h
```

## 🆘 Получение помощи

### Сбор информации для отчета об ошибке:
```bash
# Создание отчета
echo "=== MarketingBot Debug Report ===" > debug_report.txt
echo "Date: $(date)" >> debug_report.txt
echo "Python: $(python3 --version)" >> debug_report.txt
echo "OS: $(uname -a)" >> debug_report.txt
echo "" >> debug_report.txt

echo "=== Environment ===" >> debug_report.txt
python3 -c "import os; print('Token:', 'SET' if os.getenv('TELEGRAM_TOKEN') else 'NOT SET')" >> debug_report.txt
echo "WebApp URL: $WEBAPP_URL" >> debug_report.txt
echo "" >> debug_report.txt

echo "=== Last 20 log lines ===" >> debug_report.txt
tail -20 bot.log >> debug_report.txt 2>/dev/null || echo "No log file found" >> debug_report.txt

echo "=== Dependencies ===" >> debug_report.txt
pip list | grep -E "(requests|gspread|dotenv)" >> debug_report.txt

cat debug_report.txt
```

### Контакты для поддержки:
- 📖 Документация: `docs/`
- 🐛 Баг-репорты: создайте issue с debug_report.txt
- 💬 Вопросы: проверьте FAQ в документации

## 🔄 Процедура восстановления

### При критических ошибках:
1. **Остановите бота**: `pkill -f "python.*bot.py"`
2. **Создайте бэкап**: `cp .env .env.backup`
3. **Проверьте логи**: `tail -50 bot.log`
4. **Восстановите из бэкапа**: `git checkout HEAD -- .`
5. **Перезапустите**: `python3 bot.py`

### При проблемах с данными:
1. **Проверьте Google Sheets**: убедитесь в доступности
2. **Проверьте service account**: права доступа
3. **Используйте fallback**: временно отключите Sheets
4. **Восстановите подключение**: обновите credentials

## 📱 Проблемы с мобильной версией Telegram

### Проблема с авторизацией через мобильную версию:
- **Симптомы**: Авторизация не проходит через мобильную версию Telegram, но работает через веб-версию
- **Причина**: Вероятно, связано с особенностями обработки WebApp в мобильной версии Telegram
- **Решение**: Используйте веб-версию Telegram для авторизации
- **Дальнейшие действия**:
  - Используйте Context7 MCP для изучения специфики работы с мобильной версией
  - Проверьте документацию по Telegram WebApp API для мобильных клиентов
  - Исследуйте особенности обработки `sendData()` в мобильных браузерах

Помните: большинство проблем решается перезапуском бота и проверкой переменных окружения! 🚀
