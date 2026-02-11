# ⚠️ ПРАВИЛА РАЗРАБОТКИ И ТЕСТИРОВАНИЯ

> [!IMPORTANT]
> **Запрет локального запуска требует осторожности при тестировании (только через сервер).**

## 🚫 **КРИТИЧЕСКОЕ ПРАВИЛО: ЛОКАЛЬНЫЙ ЗАПУСК БОТА ЗАПРЕЩЕН**

### Запрещено:
- ❌ **НИКОГДА не запускать `bot.py` локально**
- ❌ **НИКОГДА не использовать `python bot.py` на локальной машине**
- ❌ **НИКОГДА не тестировать бота локально**

### Почему это важно:
Telegram API **не позволяет** двум ботам с одним токеном работать одновременно. Если запустить бота локально, серверный бот получит ошибку `409 Conflict` и перестанет получать сообщения от пользователей.

### Правильный подход:

#### ✅ Для тестирования бота:
1. **Коммит и пуш изменений в GitHub:**
   ```bash
   git add .
   git commit -m "описание изменений"
   git push origin main
   ```

2. **Деплой на сервер:**
   ```bash
   ssh -i ~/.ssh/ssh-key-1770366966512/ssh-key-1770366966512 marketing@89.169.176.108 \
     "cd /home/marketing/marketingbot && git pull && sudo systemctl restart marketingbot-bot.service"
   ```

3. **Тестирование через Telegram:**
   - Отправить сообщение боту в Telegram
   - Проверить логи на сервере:
   ```bash
   ssh -i ~/.ssh/ssh-key-1770366966512/ssh-key-1770366966512 marketing@89.169.176.108 \
     "journalctl -u marketingbot-bot.service -f"
   ```

#### ✅ Для локальной разработки:
- **Разрешено:** Писать код, проверять синтаксис (`ruff check .`)
- **Разрешено:** Запускать тесты (`pytest`)
- **ЗАПРЕЩЕНО:** Запускать `bot.py`

#### ✅ Как проверить, что бот работает на сервере:
```bash
# Проверка процесса на сервере
ssh -i ~/.ssh/ssh-key-1770366966512/ssh-key-1770366966512 marketing@89.169.176.108 \
  "ps aux | grep 'python.*bot.py' | grep -v grep"

# Проверка статуса сервиса
ssh -i ~/.ssh/ssh-key-1770366966512/ssh-key-1770366966512 marketing@89.169.176.108 \
  "sudo systemctl status marketingbot-bot.service"

# Проверка отсутствия локальных процессов
ps aux | grep 'python.*bot.py' | grep -v grep
# Результат: должно быть пусто (exit code 1)
```

#### ✅ Рабочий процесс:
1. **Написать код** локально
2. **Проверить линтер:** `ruff check .`
3. **Закоммитить:** `git commit -m "..."`
4. **Запушить:** `git push origin main`
5. **Деплой на сервер** через SSH
6. **Тестировать** через Telegram

---

## 🎯 Гарантия серверного тестирования

### Проверка перед тестированием:
```bash
# 1. Убедиться, что локально нет процессов бота
ps aux | grep 'python.*bot.py' | grep -v grep
# Должно быть пусто

# 2. Убедиться, что бот работает на сервере
ssh -i ~/.ssh/ssh-key-1770366966512/ssh-key-1770366966512 marketing@89.169.176.108 \
  "systemctl is-active marketingbot-bot.service"
# Должно быть: active
```

### Workflow для проверки изменений:
```bash
# scripts/deploy_and_test.sh (использовать этот скрипт для деплоя)
#!/bin/bash
set -e

echo "1️⃣ Проверка отсутствия локальных процессов..."
if ps aux | grep 'python.*bot.py' | grep -v grep > /dev/null; then
    echo "❌ ОШИБКА: Обнаружен локальный процесс bot.py!"
    echo "Остановите его перед деплоем."
    exit 1
fi

echo "2️⃣ Пуш изменений в GitHub..."
git push origin main

echo "3️⃣ Деплой на сервер..."
ssh -i ~/.ssh/ssh-key-1770366966512/ssh-key-1770366966512 marketing@89.169.176.108 \
  "cd /home/marketing/marketingbot && git pull && sudo systemctl restart marketingbot-bot.service"

echo "4️⃣ Проверка статуса..."
ssh -i ~/.ssh/ssh-key-1770366966512/ssh-key-1770366966512 marketing@89.169.176.108 \
  "sudo systemctl status marketingbot-bot.service | head -20"

echo "✅ Деплой завершен! Можно тестировать через Telegram."
```

---

## 📝 Памятка для разработчика

> **Если хочешь протестировать бота — используй серверную версию через Telegram!**
> 
> Локальный запуск = конфликт = серверный бот перестает работать для всех пользователей!

