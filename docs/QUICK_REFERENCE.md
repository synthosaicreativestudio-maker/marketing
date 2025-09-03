# ⚡ Быстрый справочник Marketing Bot

## 🚀 Быстрый старт

### **Запуск бота**
```bash
# Простой запуск
python3 bot.py

# Через manage_bot.py
python3 manage_bot.py start

# Через скрипт (macOS)
./run_single_bot.sh
```

### **Управление**
```bash
# Статус
python3 manage_bot.py status

# Остановка
python3 manage_bot.py stop

# Перезапуск
python3 manage_bot.py restart

# Логи
python3 manage_bot.py logs -f
```

## 🚨 Критические проблемы (исправить СЕЙЧАС)

### **1. bot.py:1652 - Незакрытый if**
```python
# ИСПРАВИТЬ:
if openai_client.is_available():
    logger.info("✓ OpenAI API доступен")  # ← ДОБАВИТЬ ЭТУ СТРОКУ
else:
    logger.warning("⚠ OpenAI API недоступен - AI функции отключены")
```

### **2. start_production_bot.py:18 - Неполный импорт**
```python
# ИСПРАВИТЬ:
# Удалить строку 18 или добавить полный импорт
from some_module import SingleInstanceController
```

### **3. run_single_bot.sh:52 - Неопределенная переменная**
```bash
# ИСПРАВИТЬ:
release_lock() {
    if [ -f "$LOCK_FILE" ]; then
        local lock_pid=$(cat "$LOCK_FILE" 2>/dev/null)  # ← ДОБАВИТЬ ЭТУ СТРОКУ
        if [ "$lock_pid" = "$$" ]; then
            rm -f "$LOCK_FILE"
            echo "🔓 Блокировка освобождена"
        fi
    fi
}
```

### **4. auth_cache.py - Race condition**
```python
# ДОБАВИТЬ в начало класса:
import threading

class AuthCache:
    def __init__(self, persistence_file: str = 'auth_cache.json'):
        self._lock = threading.Lock()  # ← ДОБАВИТЬ
        # ... остальной код

# ОБЕРНУТЬ критические методы:
def set_user_authorized(self, user_id: int, is_authorized: bool, partner_code: str = '', phone: str = ''):
    with self._lock:  # ← ДОБАВИТЬ
        self.user_cache[user_id] = {
            'is_authorized': is_authorized,
            'auth_timestamp': time.time(),
            'partner_code': partner_code,
            'phone': phone
        }
        self._save_to_file()
```

## 📁 Структура проекта

```
@marketing/
├── bot.py                    # Основной модуль бота
├── config.py                 # Конфигурация
├── sheets_client.py          # Google Sheets клиент
├── promotions_client.py      # Клиент акций
├── openai_client.py          # OpenAI клиент
├── auth_cache.py             # Кэш авторизации
├── mcp_context_v7.py         # MCP контекст
├── error_handler.py          # Обработка ошибок
├── performance_monitor.py    # Мониторинг
├── manage_bot.py             # Управление ботом
├── docs/                     # Документация
│   ├── README.md
│   ├── PROJECT_JOURNAL.md
│   ├── TECHNICAL_ARCHITECTURE.md
│   ├── ISSUES_AND_IMPROVEMENTS.md
│   ├── API_REFERENCE.md
│   ├── DEPLOYMENT_GUIDE.md
│   ├── MAINTENANCE_GUIDE.md
│   ├── CHECKLIST_AND_ROADMAP.md
│   ├── DAILY_PROGRESS.md
│   └── QUICK_REFERENCE.md
├── .env                      # Переменные окружения
├── credentials.json          # Google API ключи
└── requirements.txt          # Зависимости
```

## 🔧 Основные команды

### **Команды бота**
- `/start` - приветствие и авторизация
- `/menu` - доступ к личному кабинету
- `/auth <код> <телефон>` - авторизация через чат
- `/reply <код> <текст>` - ответ специалиста
- `/new_chat` - новый диалог
- `/force_update` - обновление интерфейса
- `/test_promotions` - тест акций

### **Переменные окружения**
```bash
TELEGRAM_TOKEN=your_bot_token
SHEET_URL=your_auth_sheet_url
TICKETS_SHEET_URL=your_tickets_sheet_url
PROMOTIONS_SHEET_URL=your_promotions_sheet_url
OPENAI_API_KEY=sk-your_key
OPENAI_ASSISTANT_ID=asst-your_id
ADMIN_TELEGRAM_ID=123456789,987654321
```

## 🐛 Частые проблемы

### **Бот не запускается**
```bash
# Проверить токен
echo $TELEGRAM_TOKEN

# Проверить зависимости
pip install -r requirements.txt

# Проверить логи
tail -f bot.log
```

### **Ошибки Google Sheets**
```bash
# Проверить credentials.json
python3 -c "import json; print(json.load(open('credentials.json')))"

# Проверить доступ к таблицам
# Убедиться что Service Account имеет доступ
```

### **Ошибки OpenAI**
```bash
# Проверить API ключ
python3 -c "from openai_client import openai_client; print(openai_client.is_available())"
```

### **Проблемы с авторизацией**
```bash
# Очистить кэш
rm -f auth_cache.json mcp_context_data.json

# Перезапустить
python3 manage_bot.py restart
```

## 📊 Мониторинг

### **Проверка статуса**
```bash
# Статус бота
python3 manage_bot.py status

# Процессы
ps aux | grep bot.py

# Логи
tail -f bot.log

# Ошибки
grep -i error bot.log | tail -10
```

### **Метрики**
```bash
# Время работы
grep "uptime" bot.log | tail -1

# Количество запросов
grep -c "request" bot.log

# Успешные операции
grep -c "successful" bot.log

# Ошибки
grep -c "failed" bot.log
```

## 🔄 Git команды

### **Основные**
```bash
# Статус
git status

# Добавить изменения
git add .

# Коммит
git commit -m "Описание изменений"

# Откат к точке отката
git checkout rollback-point-20250903-085717

# Вернуться к main
git checkout main
```

### **Точки отката**
```bash
# Список тегов
git tag -l

# Откат к точке отката
git checkout rollback-point-20250903-085717

# Создать новую точку отката
git tag -a "rollback-point-$(date +%Y%m%d-%H%M%S)" -m "Описание"
```

## 📚 Документация

### **Основные документы**
- **Журнал проекта**: `docs/PROJECT_JOURNAL.md`
- **Архитектура**: `docs/TECHNICAL_ARCHITECTURE.md`
- **Проблемы**: `docs/ISSUES_AND_IMPROVEMENTS.md`
- **API**: `docs/API_REFERENCE.md`
- **Развертывание**: `docs/DEPLOYMENT_GUIDE.md`
- **Обслуживание**: `docs/MAINTENANCE_GUIDE.md`
- **Чек-лист**: `docs/CHECKLIST_AND_ROADMAP.md`
- **Прогресс**: `docs/DAILY_PROGRESS.md`

### **Обновление документации**
```bash
# Обновить дату в заголовках
find docs/ -name "*.md" -exec sed -i "s/Последнее обновление: .*/Последнее обновление: $(date '+%Y-%m-%d %H:%M')/" {} \;

# Проверить ссылки
markdown-link-check docs/*.md

# Проверить синтаксис
markdownlint docs/*.md
```

## 🎯 Приоритеты

### **P1 - Критические (исправить СЕЙЧАС)**
1. bot.py:1652 - незакрытый if
2. start_production_bot.py:18 - неполный импорт
3. run_single_bot.sh:52 - неопределенная переменная
4. auth_cache.py - race condition

### **P2 - Архитектурные (неделя 1-2)**
1. Рефакторинг класса Bot
2. Dependency Injection
3. Улучшение error handling

### **P3 - Производительность (неделя 2-3)**
1. Асинхронные операции
2. Connection pooling
3. Оптимизация кэша

### **P4 - Новые функции (неделя 4-6)**
1. Мониторинг и метрики
2. Тестирование
3. Безопасность

## 📞 Контакты

### **Ресурсы**
- **Документация**: `docs/` папка
- **Issues**: `docs/ISSUES_AND_IMPROVEMENTS.md`
- **Точка отката**: `rollback-point-20250903-085717`

### **Поддержка**
- **Логи**: `bot.log`
- **Диагностика**: `python3 advanced_diagnostics.py`
- **Статус**: `python3 manage_bot.py health`

---

**Последнее обновление**: 2025-01-03 08:57
**Версия**: 1.0
**Статус**: Актуально
