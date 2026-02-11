#!/bin/bash
# Скрипт мониторинга здоровья бота на сервере

SSH_KEY="$HOME/.ssh/ssh-key-1767684261599/ssh-key-1767684261599"
SERVER="ubuntu@158.160.0.127"
SERVICE="marketingbot-bot.service"

echo "🔍 МОНИТОРИНГ ЗДОРОВЬЯ БОТА"
echo "=============================="
echo ""

# 1. Проверка статуса сервиса
echo "📊 Статус сервиса:"
STATUS=$(ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no "$SERVER" \
  "systemctl is-active $SERVICE" 2>/dev/null)

if [ "$STATUS" = "active" ]; then
  echo "✅ Сервис активен"
else
  echo "❌ ПРОБЛЕМА: Сервис не активен (статус: $STATUS)"
  exit 1
fi

# 2. Время работы без перезапусков
echo ""
echo "⏱ Uptime:"
ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no "$SERVER" \
  "systemctl show $SERVICE --property=ActiveEnterTimestamp,NRestarts" 2>/dev/null | \
  while IFS='=' read -r key value; do
    if [ "$key" = "ActiveEnterTimestamp" ]; then
      echo "  Запущен: $value"
    elif [ "$key" = "NRestarts" ]; then
      if [ "$value" -eq 0 ]; then
        echo "  ✅ Перезапусков: $value (стабильно)"
      else
        echo "  ⚠️  Перезапусков: $value"
      fi
    fi
  done

# 3. Потребление ресурсов
echo ""
echo "💾 Ресурсы:"
ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no "$SERVER" \
  "systemctl status $SERVICE --no-pager" 2>/dev/null | grep -E "(Memory|CPU)" | \
  while read -r line; do
    echo "  $line"
  done

# 4. Проверка логов на критические ошибки (последние 5 минут)
echo ""
echo "🚨 Критические ошибки (последние 5 минут):"
ERRORS=$(ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no "$SERVER" \
  "sudo journalctl -u $SERVICE --since '5 minutes ago' --no-pager | grep -E '(CRITICAL|ERROR|409 Conflict)' | wc -l" 2>/dev/null)

if [ "$ERRORS" -eq 0 ]; then
  echo "  ✅ Критических ошибок не обнаружено"
else
  echo "  ⚠️  Обнаружено ошибок: $ERRORS"
  echo ""
  echo "  Последние ошибки:"
  ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no "$SERVER" \
    "sudo journalctl -u $SERVICE --since '5 minutes ago' --no-pager | grep -E '(CRITICAL|ERROR)' | tail -5" 2>/dev/null | \
    sed 's/^/    /'
fi

# 5. Проверка Event Loop (наличие успешных getUpdates)
echo ""
echo "🔄 Event Loop (активность):"
UPDATES=$(ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no "$SERVER" \
  "sudo journalctl -u $SERVICE --since '1 minute ago' --no-pager | grep 'getUpdates.*200 OK' | wc -l" 2>/dev/null)

if [ "$UPDATES" -gt 0 ]; then
  echo "  ✅ Event Loop активен ($UPDATES запросов за последнюю минуту)"
else
  echo "  ⚠️  Event Loop неактивен или заблокирован"
fi

# 6. Проверка на дублирование процессов
echo ""
echo "🔢 Процессы бота:"
PROCESSES=$(ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no "$SERVER" \
  "ps aux | grep 'python.*bot.py' | grep -v grep | wc -l" 2>/dev/null)

if [ "$PROCESSES" -eq 1 ]; then
  echo "  ✅ Запущен только один процесс (корректно)"
elif [ "$PROCESSES" -eq 0 ]; then
  echo "  ❌ КРИТИЧНО: Процессы бота не найдены!"
else
  echo "  ⚠️  ПРОБЛЕМА: Обнаружено $PROCESSES процессов (должен быть 1)"
fi

# Итоговая оценка
echo ""
echo "=============================="
if [ "$STATUS" = "active" ] && [ "$ERRORS" -eq 0 ] && [ "$PROCESSES" -eq 1 ] && [ "$UPDATES" -gt 0 ]; then
  echo "✅ СТАТУС: Бот работает стабильно"
  exit 0
else
  echo "⚠️  СТАТУС: Обнаружены потенциальные проблемы"
  exit 1
fi
