# 🔧 Устранение неполадок MarketingBot v3.2

## 🚨 Частые проблемы и решения (PythonAnywhere)

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

#### Проблема с webhook (PythonAnywhere):
```bash
# Проверка webhook
curl -X GET "https://api.telegram.org/bot<TOKEN>/getWebhookInfo"

# Установка webhook
curl -X POST "https://api.telegram.org/bot<TOKEN>/setWebhook" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://yourusername.pythonanywhere.com/webhook"}'
```

#### Проблема с сетью:
```bash
# Проверка подключения к Telegram API
curl -I https://api.telegram.org

# Проверка webhook на PythonAnywhere
curl -I https://yourusername.pythonanywhere.com/webhook

# Проверка DNS
nslookup api.telegram.org
```

#### Проблема с PythonAnywhere:
```bash
# Проверка версии Python
python3 --version

# Установка зависимостей
pip3 install --user -r requirements.txt

# Проверка путей
python3 -c "import sys; print('Python path:', sys.path)"
```

#### Проблема с процессом:
```bash
# Проверка запущенных процессов
pgrep -f "python.*bot.py"

# Запуск бота на PythonAnywhere
python3 bot.py

# Запуск в фоне
nohup python3 bot.py > bot.log 2>&1 &

# Перезапуск бота
pkill -f "python.*bot.py"
python3 bot.py
```

#### Проблема с webhook на PythonAnywhere:
```bash
# Проверка webhook
curl -X GET "https://api.telegram.org/bot<TOKEN>/getWebhookInfo"

# Удаление webhook
curl -X POST "https://api.telegram.org/bot<TOKEN>/deleteWebhook"

# Установка нового webhook
curl -X POST "https://api.telegram.org/bot<TOKEN>/setWebhook" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://yourusername.pythonanywhere.com/webhook"}'
```

### 2. WebApp не открывается

**Симптомы:**
- Кнопка "Авторизоваться" не работает
- WebApp показывает ошибку или не загружается
- Ошибка при открытии веб-приложения

**Решения:**

#### Проверка WEBAPP_URL:
```bash
# Проверка URL WebApp
python3 -c "from handlers import get_web_app_url; print('WebApp URL:', get_web_app_url())"

# Проверка доступности файлов
curl -I https://synthosaicreativestudio-maker.github.io/marketing/index.html
curl -I https://synthosaicreativestudio-maker.github.io/marketing/menu.html
```

#### Проверка переменной:
```bash
# Проверка переменной
echo $WEBAPP_URL

# Проверка доступности URL
curl -I $WEBAPP_URL
```

#### Проверка файлов WebApp:
```bash
# Проверка наличия файлов
ls -la index.html menu.html app.js

# Проверка содержимого
head -5 index.html
head -5 menu.html
head -5 app.js
```

#### Проблемы с HTTPS:
- WebApp требует HTTPS для работы в Telegram
- PythonAnywhere предоставляет HTTPS из коробки
- Проверьте настройки в .env:
```bash
# Проверка HTTPS
curl -I https://synthosaicreativestudio-maker.github.io/marketing/index.html

# Проверка настроек
grep WEBAPP_URL .env
```

### 3. Ошибки авторизации

**Симптомы:**
- "Партнёр не найден в базе"
- Пользователи не могут авторизоваться
- Ошибки при проверке статуса авторизации
- Ошибки при обработке данных
- Показывается кнопка авторизации вместо меню

**Решения:**

#### Проверка Google Sheets:
```bash
# Проверка подключения к Google Sheets
python3 -c "from sheets import _load_service_account; print('Google Sheets connection OK')"

# Проверка данных в таблице
python3 -c "from sheets import get_sheet_data; print('Sheet data:', get_sheet_data()[:3])"

# Проверка Service Account
python3 -c "from sheets import _load_service_account; sa = _load_service_account(); print('Service Account:', sa.service_account_email)"
```

#### Проблемы с Google Sheets:
```bash
# Проверка service account
python3 -c "import json; print(json.loads(open('.env').read().split('GCP_SA_JSON=')[1].split('\n')[0])['client_email'])"

# Проверка прав доступа
python3 -c "from sheets import _load_service_account; sa = _load_service_account(); print('Service Account email:', sa.service_account_email)"

# Проверка таблицы авторизации
python3 -c "from sheets import get_sheet_data; data = get_sheet_data(); print('Authorization data:', data[:3] if data else 'No data')"
```

# Проверка доступа к таблице
python3 -c "from sheets import _get_client_and_sheet; client, sheet = _get_client_and_sheet(); print('Sheets OK')"
```

#### Проблемы с кешированием:
```bash
# Сброс кеша авторизации
rm -f auth_cache.json

# Перезапуск бота
python3 bot.py
```

#### Fallback авторизация:
- Если Google Sheets не настроены, используется простая проверка
- Тестовые данные: код `111098`, телефон с `1055`

### 4. Проблемы с системой обращений

**Симптомы:**
- Обращения не создаются
- Статусы не обновляются
- Ответы специалистов не отправляются

**Решения:**

#### Проверка AppealsService:
```bash
# Проверка сервиса обращений
python3 -c "from appeals_service import AppealsService; as = AppealsService(); print('Appeals service OK')"

# Проверка создания обращения
python3 -c "from appeals_service import AppealsService; as = AppealsService(); print('Test appeal:', as.create_appeal('TEST', '123', 'Test User', 123456789, 'Test message'))"
```

#### Проверка ResponseMonitor:
```bash
# Проверка мониторинга ответов
python3 -c "from response_monitor import ResponseMonitor; rm = ResponseMonitor(); print('Response monitor OK')"

# Проверка логов
grep -i "appeal\|status\|response" bot.log | tail -10
```

#### Проблема с кнопками WebApp:
```bash
# Проверка переменных WebApp
echo "WEB_APP_URL: $WEB_APP_URL"

# Проверка генерации URL
python3 -c "from handlers import get_web_app_url, get_spa_menu_url; print('Auth URL:', get_web_app_url()); print('Menu URL:', get_spa_menu_url())"
```

### 5. Проблемы с OpenAI

**Симптомы:**
- ИИ не отвечает на сообщения
- Ошибки API OpenAI
- Медленные ответы

**Решения:**

#### Проверка API ключа:
```bash
# Проверка API ключа
python3 -c "import os; from dotenv import load_dotenv; load_dotenv(); print('OpenAI Key:', 'OK' if os.getenv('OPENAI_API_KEY') else 'MISSING')"

# Проверка Assistant ID
python3 -c "import os; from dotenv import load_dotenv; load_dotenv(); print('Assistant ID:', os.getenv('OPENAI_ASSISTANT_ID'))"
```

#### Проверка подключения:
```bash
# Проверка сервиса OpenAI
python3 -c "from openai_service import OpenAIService; oai = OpenAIService(); print('OpenAI service OK')"

# Тест запроса
python3 -c "from openai_service import OpenAIService; oai = OpenAIService(); print('Test response:', oai.get_response('Test message', 123456789))"
```

### 6. Проблемы с PythonAnywhere

**Симптомы:**
- Бот не запускается
- Ошибки импорта модулей
- Проблемы с webhook

**Решения:**

#### Проверка версии Python:
```bash
# Проверка версии Python
python3 --version

# Установка зависимостей
pip3 install --user -r requirements.txt

# Проверка путей
python3 -c "import sys; print('Python path:', sys.path)"
```

#### Проверка webhook:
```bash
# Проверка webhook
curl -X GET "https://api.telegram.org/bot<TOKEN>/getWebhookInfo"

# Удаление webhook
curl -X POST "https://api.telegram.org/bot<TOKEN>/deleteWebhook"

# Установка нового webhook
curl -X POST "https://api.telegram.org/bot<TOKEN>/setWebhook" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://yourusername.pythonanywhere.com/webhook"}'
```

## 🔍 Диагностика

### Полная проверка системы:
```bash
# Диагностика всех сервисов
python3 -c "
import os
from dotenv import load_dotenv
load_dotenv()

print('=== Диагностика MarketingBot v3.2 ===')
print(f'Telegram Token: {\"✓\" if os.getenv(\"TELEGRAM_TOKEN\") else \"✗\"}')
print(f'OpenAI API Key: {\"✓\" if os.getenv(\"OPENAI_API_KEY\") else \"✗\"}')
print(f'OpenAI Assistant ID: {\"✓\" if os.getenv(\"OPENAI_ASSISTANT_ID\") else \"✗\"}')
print(f'Sheets ID: {\"✓\" if os.getenv(\"SHEET_ID\") else \"✗\"}')
print(f'Appeals Sheets ID: {\"✓\" if os.getenv(\"APPEALS_SHEET_ID\") else \"✗\"}')
print(f'Promotions Sheets ID: {\"✓\" if os.getenv(\"PROMOTIONS_SHEET_ID\") else \"✗\"}')
print(f'WebApp URL: {os.getenv(\"WEB_APP_URL\", \"✗\")}')
print(f'Webhook URL: {os.getenv(\"WEBHOOK_URL\", \"✗\")}')
print(f'GCP SA JSON: {\"✓\" if os.getenv(\"GCP_SA_JSON\") else \"✗\"}')
"
```

### Тест функций:
```bash
# Тест авторизации
python3 -c "from auth_service import AuthService; auth = AuthService(); print('Auth service test:', auth.get_user_auth_status(123456789))"

# Тест обращений
python3 -c "from appeals_service import AppealsService; appeals = AppealsService(); print('Appeals service test:', appeals.create_appeal('TEST', '123', 'Test User', 123456789, 'Test message'))"

# Тест OpenAI
python3 -c "from openai_service import OpenAIService; openai = OpenAIService(); print('OpenAI service test:', openai.get_response('Test message', 123456789))"

# Тест акций
python3 -c "from promotions_api import get_active_promotions; promotions = get_active_promotions(); print('Promotions test:', len(promotions), 'active promotions')"
```

## 📊 Мониторинг

### Просмотр логов:
```bash
# Все логи
tail -f bot.log

# Только ошибки
tail -f bot.log | grep -i "error\|exception\|traceback"

# Только обращения
tail -f bot.log | grep -i "appeal\|status\|response"

# Только авторизацию
tail -f bot.log | grep -i "auth\|authorization\|login"

# Только акции
tail -f bot.log | grep -i "promotion\|акция\|уведомление"
```

### Проверка производительности:
```bash
# Время ответа
grep "Response time" bot.log | tail -10

# Количество обращений
grep "Appeal created" bot.log | wc -l

# Ошибки API
grep "API error" bot.log | wc -l

# Статистика авторизации
grep "Authorization" bot.log | wc -l
```

## 🆘 Экстренные меры

### Перезапуск бота:
```bash
# Остановка
pkill -f "python3 bot.py"

# Запуск
python3 bot.py

# Запуск в фоне
nohup python3 bot.py > bot.log 2>&1 &
```

### Сброс кэша:
```bash
# Удаление кэша авторизации
rm -f auth_cache.json

# Перезапуск бота
python3 bot.py
```

### Восстановление из бэкапа:
```bash
# Восстановление .env
cp .env.backup .env

# Восстановление кода
git checkout HEAD~1

# Перезапуск
python3 bot.py
```

### Сброс webhook:
```bash
# Удаление webhook
curl -X POST "https://api.telegram.org/bot<TOKEN>/deleteWebhook"

# Установка нового webhook
curl -X POST "https://api.telegram.org/bot<TOKEN>/setWebhook" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://yourusername.pythonanywhere.com/webhook"}'
```

## 📞 Поддержка

Если проблема не решается с помощью этого руководства:

1. **Проверьте логи** - найдите конкретную ошибку
2. **Создайте issue** - опишите проблему и приложите логи
3. **Обратитесь к разработчику** - предоставьте полную информацию

### Информация для поддержки:
```bash
# Сбор информации о системе
echo "=== System Info ==="
python3 --version
pip list | grep -E "(telegram|openai|gspread|flask)"
echo "=== Bot Status ==="
ps aux | grep "python3 bot.py"
echo "=== Recent Logs ==="
tail -20 bot.log
echo "=== Webhook Status ==="
curl -X GET "https://api.telegram.org/bot<TOKEN>/getWebhookInfo"
```

## 🎯 Частые проблемы v3.2

### Проблема с автоматическим изменением статуса на "решено"
**Симптомы:**
- Статус автоматически меняется на "решено" после ответа специалиста
- Пропускается статус "в работе"

**Решение:**
```bash
# Проверка response_monitor.py
grep -n "автоматически.*решено" response_monitor.py

# Исправление: убрать автоматическое изменение статуса
# Статус должен оставаться "в работе" после ответа специалиста
```

### Проблема с дублированием сообщений
**Симптомы:**
- Бот отправляет два ответа на одно сообщение
- Дублирование в логах

**Решение:**
```bash
# Проверка handlers.py
grep -n "reply_text" handlers.py

# Исправление: убрать дублирующие вызовы
```

### Проблема с кешированием авторизации
**Симптомы:**
- Пользователи не могут авторизоваться
- Ошибки "Партнер не найден"

**Решение:**
```bash
# Сброс кеша
rm -f auth_cache.json

# Перезапуск бота
python3 bot.py
```

## 📋 Чек-лист для диагностики

### ✅ Проверка основных компонентов
- [ ] Telegram Bot API работает
- [ ] Google Sheets подключение работает
- [ ] OpenAI API работает
- [ ] WebApp доступен по HTTPS
- [ ] Webhook настроен правильно

### ✅ Проверка функций
- [ ] Авторизация работает
- [ ] Обращения создаются
- [ ] Статусы обновляются
- [ ] Ответы специалистов отправляются
- [ ] Акции отображаются

### ✅ Проверка производительности
- [ ] Время ответа < 2 секунд
- [ ] Нет ошибок в логах
- [ ] Кеширование работает
- [ ] Мониторинг активен

## 🚀 Рекомендации по оптимизации

### Для PythonAnywhere:
1. **Используйте Python 3.10** - более стабильная версия
2. **Настройте автозапуск** - через Tasks в панели
3. **Мониторьте логи** - регулярно проверяйте bot.log
4. **Обновляйте зависимости** - pip install --user -r requirements.txt

### Для масштабирования:
1. **Увеличьте TTL кеша** - до 10-15 минут
2. **Оптимизируйте запросы** - к Google Sheets
3. **Добавьте мониторинг** - метрики производительности
4. **Настройте алерты** - при критических ошибках

## 📞 Контакты для поддержки

- **GitHub Issues**: [Создать issue](https://github.com/synthosaicreativestudio-maker/marketing/issues)
- **Telegram**: @synthosaicreativestudio
- **Email**: support@synthosaicreativestudio.com

---

**Версия документации:** v3.2  
**Последнее обновление:** 9 октября 2025  
**Статус:** ✅ Актуально
