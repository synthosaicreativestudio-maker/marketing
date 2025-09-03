# 🔧 Руководство по обслуживанию Marketing Bot

## 📅 Регулярные задачи

### **Ежедневно**
- [ ] Проверить статус бота: `python3 manage_bot.py status`
- [ ] Просмотреть логи на ошибки: `grep -i error bot.log`
- [ ] Проверить метрики производительности
- [ ] Убедиться в доступности внешних сервисов

### **Еженедельно**
- [ ] Очистить старые логи (старше 30 дней)
- [ ] Проверить размер кэш-файлов
- [ ] Обновить статистику использования
- [ ] Проверить доступность Google Sheets

### **Ежемесячно**
- [ ] Обновить зависимости: `pip install -r requirements.txt --upgrade`
- [ ] Проверить безопасность API ключей
- [ ] Анализ производительности и оптимизация
- [ ] Резервное копирование конфигурации

## 🔍 Мониторинг

### **Ключевые метрики**

#### **Производительность**
```bash
# Время ответа
grep "execution_time" bot.log | tail -10

# Процент успешных операций
grep -c "successful" bot.log
grep -c "failed" bot.log
```

#### **Использование ресурсов**
```bash
# Память
ps aux | grep bot.py | awk '{print $6/1024 " MB"}'

# CPU
top -p $(pgrep -f bot.py) -n 1 | grep bot.py
```

#### **Внешние сервисы**
```bash
# Google Sheets доступность
grep -c "Google Sheets" bot.log | tail -1

# OpenAI доступность
grep -c "OpenAI" bot.log | tail -1

# Telegram API
grep -c "Telegram" bot.log | tail -1
```

### **Алерты и уведомления**

#### **Критические алерты**
- Бот не отвечает более 5 минут
- Ошибки авторизации > 10% за час
- Ошибки внешних API > 20% за час
- Использование памяти > 80%

#### **Предупреждения**
- Медленные ответы > 10 секунд
- Высокий процент ошибок > 5%
- Большой размер кэш-файлов
- Много неудачных попыток авторизации

## 🧹 Очистка и оптимизация

### **Очистка логов**
```bash
# Архивировать старые логи
tar -czf logs-$(date +%Y%m%d).tar.gz *.log

# Удалить логи старше 30 дней
find . -name "*.log" -mtime +30 -delete

# Очистить текущий лог (сохранить последние 1000 строк)
tail -1000 bot.log > bot.log.tmp && mv bot.log.tmp bot.log
```

### **Очистка кэша**
```bash
# Очистить кэш авторизации (осторожно!)
python3 -c "
from auth_cache import auth_cache
auth_cache.clear_all_caches()
print('Auth cache cleared')
"

# Очистить MCP контекст
rm -f mcp_context_data.json

# Перезапустить бота для пересоздания кэша
python3 manage_bot.py restart
```

### **Оптимизация производительности**
```bash
# Проверить размер кэш-файлов
ls -lh *.json

# Анализ медленных операций
grep "execution_time" bot.log | sort -k2 -nr | head -10

# Проверить количество активных пользователей
grep -c "authorized" bot.log | tail -1
```

## 🔒 Безопасность

### **Ротация ключей**
```bash
# Создать backup текущих ключей
cp .env .env.backup.$(date +%Y%m%d)

# Обновить ключи в .env
# Перезапустить бота
python3 manage_bot.py restart
```

### **Проверка доступа**
```bash
# Проверить права доступа к файлам
ls -la .env credentials.json

# Проверить доступ к Google Sheets
python3 -c "
from sheets_client import GoogleSheetsClient
client = GoogleSheetsClient('credentials.json', 'your_sheet_url', 'worksheet')
print('Sheets access OK')
"
```

### **Аудит логов**
```bash
# Поиск подозрительной активности
grep -i "error\|failed\|blocked" bot.log | tail -20

# Анализ попыток авторизации
grep "auth" bot.log | grep -v "successful" | tail -10

# Проверка админских команд
grep "admin" bot.log | tail -10
```

## 📊 Анализ и отчеты

### **Еженедельный отчет**
```bash
#!/bin/bash
# weekly_report.sh

echo "=== Weekly Bot Report ==="
echo "Date: $(date)"
echo ""

echo "=== Uptime ==="
python3 manage_bot.py status

echo ""
echo "=== Performance ==="
echo "Total requests: $(grep -c "request" bot.log)"
echo "Successful: $(grep -c "successful" bot.log)"
echo "Failed: $(grep -c "failed" bot.log)"

echo ""
echo "=== Users ==="
echo "Auth attempts: $(grep -c "auth" bot.log)"
echo "Active users: $(grep -c "authorized" bot.log)"

echo ""
echo "=== Errors ==="
echo "Critical errors: $(grep -c "CRITICAL" bot.log)"
echo "Warnings: $(grep -c "WARNING" bot.log)"
```

### **Месячный анализ**
```bash
# Анализ трендов
grep "execution_time" bot.log | awk '{print $2}' | sort -n | tail -10

# Топ пользователей
grep "user" bot.log | awk '{print $3}' | sort | uniq -c | sort -nr | head -10

# Анализ ошибок по типам
grep "ERROR" bot.log | awk '{print $4}' | sort | uniq -c | sort -nr
```

## 🚨 Устранение неполадок

### **Бот не отвечает**
```bash
# 1. Проверить процессы
ps aux | grep bot.py

# 2. Проверить логи
tail -20 bot.log

# 3. Перезапустить
python3 manage_bot.py restart

# 4. Если не помогает - полный перезапуск
python3 manage_bot.py stop
sleep 5
python3 manage_bot.py start
```

### **Высокое использование памяти**
```bash
# 1. Проверить размер кэша
ls -lh *.json

# 2. Очистить кэш
python3 -c "from auth_cache import auth_cache; auth_cache.clear_all_caches()"

# 3. Перезапустить
python3 manage_bot.py restart

# 4. Мониторить
watch -n 5 'ps aux | grep bot.py'
```

### **Медленные ответы**
```bash
# 1. Анализ медленных операций
grep "execution_time" bot.log | sort -k2 -nr | head -10

# 2. Проверить внешние сервисы
python3 -c "from openai_client import openai_client; print(openai_client.is_available())"

# 3. Проверить Google Sheets
python3 -c "from sheets_client import GoogleSheetsClient; print('Testing...')"

# 4. Оптимизировать настройки
# Увеличить таймауты в config.py
```

### **Ошибки авторизации**
```bash
# 1. Проверить Google Sheets доступ
python3 -c "
from sheets_client import GoogleSheetsClient
client = GoogleSheetsClient('credentials.json', 'your_sheet_url', 'worksheet')
print('Sheets connection OK')
"

# 2. Очистить кэш авторизации
rm -f auth_cache.json

# 3. Проверить формат данных в таблице
# Убедиться что коды и телефоны в правильном формате

# 4. Перезапустить
python3 manage_bot.py restart
```

## 🔄 Обновления и патчи

### **Планирование обновлений**
1. **Создать backup**: `tar -czf backup-$(date +%Y%m%d).tar.gz .`
2. **Тестировать на dev**: Сначала на тестовой среде
3. **Обновить production**: В maintenance window
4. **Мониторить**: Следить за логами после обновления

### **Откат изменений**
```bash
# 1. Остановить бота
python3 manage_bot.py stop

# 2. Откатить код
git checkout rollback-point-YYYYMMDD-HHMMSS

# 3. Восстановить конфигурацию
cp .env.backup.$(date +%Y%m%d) .env

# 4. Перезапустить
python3 manage_bot.py start
```

### **Проверка после обновления**
```bash
# 1. Статус
python3 manage_bot.py status

# 2. Логи
tail -f bot.log

# 3. Функциональность
# Протестировать основные функции:
# - Авторизация
# - Отправка сообщений
# - Работа с акциями
# - Ответы специалистов
```

## 📈 Оптимизация

### **Настройки производительности**
```python
# В config.py
SCALING_CONFIG = {
    'MAX_CONCURRENT_REQUESTS': 10,  # Увеличить при высокой нагрузке
    'REQUEST_TIMEOUT': 30,          # Увеличить при медленной сети
    'CACHE_CLEANUP_INTERVAL': 3600, # Уменьшить при нехватке памяти
    'MAX_CACHE_SIZE': 10000,        # Увеличить при большом количестве пользователей
}
```

### **Мониторинг ресурсов**
```bash
# Настройка мониторинга
# Добавить в crontab:
# */5 * * * * /path/to/monitor_bot.sh

# monitor_bot.sh
#!/bin/bash
MEMORY=$(ps aux | grep bot.py | awk '{print $6/1024}')
if (( $(echo "$MEMORY > 1000" | bc -l) )); then
    echo "High memory usage: ${MEMORY}MB" | mail -s "Bot Alert" admin@example.com
fi
```

## 📞 Контакты и эскалация

### **Уровни поддержки**
1. **L1 - Мониторинг**: Автоматические проверки, базовые исправления
2. **L2 - Администрирование**: Ручные исправления, оптимизация
3. **L3 - Разработка**: Критические баги, архитектурные изменения

### **Процедуры эскалации**
- **Критические ошибки** (> 50% запросов падают) → L3 немедленно
- **Производительность** (медленные ответы) → L2 в течение часа
- **Мониторинг** (обычные алерты) → L1 в течение дня

---

**Последнее обновление**: 2025-01-03 08:57
**Версия руководства**: 1.0
**Следующий review**: Ежемесячно
