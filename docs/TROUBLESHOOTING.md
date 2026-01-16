# 🛠️ Руководство по устранению проблем бота

## ❌ Типичные проблемы и их решения

### 1. **409 Conflict: несколько процессов бота**

**Признаки:**
```
ERROR - Ошибка Telegram API: Conflict: terminated by other getUpdates request
CRITICAL - ⚠️ ОБНАРУЖЕН КОНФЛИКТ: Запущено несколько экземпляров бота!
```

**Причина:** Запущено два или более процесса бота одновременно.

**Решение:**
```bash
# 1. Найти все процессы бота
ps aux | grep 'python.*bot.py'

# 2. Убить лишние процессы (оставить только systemd)
kill -9 <PID_лишнего_процесса>

# 3. Перезапустить через systemd
sudo systemctl restart marketingbot-bot.service

# 4. Проверить, что остался только один
ps aux | grep 'python.*bot.py' | grep -v grep | wc -l
# Должно быть: 1
```

**Профилактика:**
- Всегда запускайте бота ТОЛЬКО через `systemctl`
- Перед запуском проверяйте, что старый процесс убит
- Не запускайте `python bot.py` вручную на production

---

### 2. **RuntimeWarning: coroutine was never awaited**

**Признаки:**
```
RuntimeWarning: coroutine 'function_name' was never awaited
```

**Причина:** Асинхронная функция вызвана без `await` или `asyncio.create_task()`.

**Решение:**
1. Найдите функцию в коде по имени из warning
2. Убедитесь, что перед вызовом стоит `await`:
```python
# ❌ НЕПРАВИЛЬНО
result = async_function()

# ✅ ПРАВИЛЬНО
result = await async_function()
```

3. Если вызов в `__init__`, используйте:
```python
# В __init__
asyncio.create_task(self.initialize())

# Или делайте синхронную инициализацию
```

**Код:**
- Проверьте файлы: `auth_service.py`, `appeals_service.py`, `bot.py`
- Найдите async функции без await

---

### 3. **TimeoutError / ConnectionError**

**Признаки:**
```
TimeoutError: Request timed out
ConnectionError: Failed to establish connection
```

**Причины и решения:**

**A. Проблемы с OpenAI:**
```bash
# Проверить proxy
grep OPENAI_PROXY ~/.env

# Убедиться, что proxy работает
curl -x http://37.1.212.51:8080 https://api.openai.com/v1/models
```

**B. Проблемы с Google Sheets:**
```bash
# Проверить credentials
ls -la /home/ubuntu/marketingbot/credentials.json

# Проверить права доступа к таблицам
# Откройте таблицы и убедитесь, что service account имеет доступ
```

**C. Проблемы с сетью:**
```bash
# Проверить доступность Telegram API
curl https://api.telegram.org/bot<TOKEN>/getMe

# Проверить DNS
nslookup api.telegram.org
```

**Решение - увеличить таймауты:**
```python
# В openai_service.py или bot.py
timeout = httpx.Timeout(60.0, connect=10.0)  # Было 30.0
```

---

### 4. **Рост памяти без стабилизации (утечка памяти)**

**Признаки:**
```bash
# Memory растет постоянно
systemctl status marketingbot-bot.service
# Memory: 100M → 150M → 200M → ...
```

**Диагностика:**
```bash
# Мониторить память каждые 10 минут
watch -n 600 'systemctl status marketingbot-bot.service | grep Memory'

# Если за час выросла более чем на 50M - есть утечка
```

**Решение:**
1. **Проверить кэши:**
```python
# В auth_service.py
self.auth_cache = TTLCache(maxsize=2000, ttl=300)  # Ограничение размера!
```

2. **Очистить старые данные:**
```python
# В appeals_service.py есть метод _cleanup_old_appeals
# Убедитесь, что он запускается регулярно
```

3. **Перезапуск бота раз в сутки (крайняя мера):**
```bash
# Добавить в crontab
0 4 * * * /usr/bin/systemctl restart marketingbot-bot.service
```

---

### 5. **Частые RestartSec в логах (циклические падения)**

**Признаки:**
```bash
sudo journalctl -u marketingbot-bot.service | grep "Scheduled restart"
# Видим много записей
```

**Диагностика:**
```bash
# Проверить NRestarts
systemctl show marketingbot-bot.service | grep NRestarts
# Если > 5 за час - критично

# Посмотреть последние причины падения
sudo journalctl -u marketingbot-bot.service --since "1 hour ago" | grep -E "(CRITICAL|ERROR)" | tail -20
```

**Решение:**
1. **Найти причину в логах** (обычно CRITICAL ERROR перед падением)
2. **Исправить код** согласно ошибке
3. **Если проблема в зависимостях:**
```bash
cd /home/ubuntu/marketingbot
.venv/bin/pip install --upgrade -r requirements.txt
```

4. **Если проблема в .env:**
```bash
nano /home/ubuntu/marketingbot/.env
# Проверить все переменные
```

---

## 🔍 Профилактический мониторинг

**Запускайте проверку здоровья:**
```bash
bash /Users/verakoroleva/Desktop/marketingbot/scripts/monitor_bot_health.sh
```

**Ключевые метрики для отслеживания:**
| Метрика | Норма | Проблема |
|---------|-------|----------|
| NRestarts | 0 | > 0 |
| Memory | 60-100M | > 150M или растет |
| Event Loop активность | > 0 req/min | 0 req/min |
| Процессов | 1 | != 1 |
| CRITICAL errors | 0 | > 0 |

**Автоматический мониторинг (добавить в crontab):**
```bash
# Каждые 10 минут проверять и логировать
*/10 * * * * bash /path/to/monitor_bot_health.sh >> /var/log/bot_health.log 2>&1

# Раз в час отправлять алерт при проблемах
0 * * * * bash /path/to/monitor_bot_health.sh || echo "Bot health check failed!" | mail -s "Bot Alert" admin@example.com
```

---

## 📞 Быстрая диагностика при падении

```bash
# 1. Проверить статус
sudo systemctl status marketingbot-bot.service

# 2. Последние 50 строк логов
sudo journalctl -u marketingbot-bot.service -n 50 --no-pager

# 3. Критические ошибки за последний час
sudo journalctl -u marketingbot-bot.service --since "1 hour ago" | grep -E "(CRITICAL|ERROR)"

# 4. Перезапустить
sudo systemctl restart marketingbot-bot.service

# 5. Проверить, что запустился
sleep 5 && sudo systemctl status marketingbot-bot.service
```
