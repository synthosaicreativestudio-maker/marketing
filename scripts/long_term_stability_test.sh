#!/bin/bash
# Скрипт долгосрочного тестирования стабильности бота (24+ часа)
# Хост и ключ: scripts/yandex_vm_config.sh

source "$(dirname "$0")/yandex_vm_config.sh"
SERVER="${VM_USER}@${VM_HOST}"
SERVICE="marketingbot-bot.service"
LOG_FILE="bot_stability_test_$(date +%Y%m%d_%H%M%S).log"

echo "🧪 ДОЛГОСРОЧНЫЙ ТЕСТ СТАБИЛЬНОСТИ БОТА" | tee -a "$LOG_FILE"
echo "=======================================" | tee -a "$LOG_FILE"
echo "Начало: $(date)" | tee -a "$LOG_FILE"
echo "Лог-файл: $LOG_FILE" | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"

# Базовые метрики для сравнения
INITIAL_MEMORY=$(ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no "$SERVER" \
  "systemctl show $SERVICE --property=MemoryCurrent" 2>/dev/null | cut -d= -f2)
INITIAL_TIME=$(date +%s)

echo "📊 Начальные метрики:" | tee -a "$LOG_FILE"
echo "  Память: $((INITIAL_MEMORY / 1024 / 1024)) MB" | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"

# Функция проверки
check_bot_health() {
  local iteration=$1
  local current_time=$(date +%s)
  local elapsed=$((current_time - INITIAL_TIME))
  local hours=$((elapsed / 3600))
  local minutes=$(( (elapsed % 3600) / 60 ))
  
  echo "=== Проверка #$iteration (Прошло: ${hours}ч ${minutes}мин) ===" | tee -a "$LOG_FILE"
  
  # 1. Статус сервиса
  local status=$(ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no "$SERVER" \
    "systemctl is-active $SERVICE" 2>/dev/null)
  
  if [ "$status" != "active" ]; then
    echo "❌ КРИТИЧНО: Бот не активен! Статус: $status" | tee -a "$LOG_FILE"
    return 1
  fi
  echo "✅ Статус: active" | tee -a "$LOG_FILE"
  
  # 2. Количество перезапусков
  local restarts=$(ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no "$SERVER" \
    "systemctl show $SERVICE --property=NRestarts" 2>/dev/null | cut -d= -f2)
  
  if [ "$restarts" -gt 0 ]; then
    echo "⚠️  Перезапусков: $restarts" | tee -a "$LOG_FILE"
  else
    echo "✅ Перезапусков: 0 (стабильно)" | tee -a "$LOG_FILE"
  fi
  
  # 3. Потребление памяти
  local current_memory=$(ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no "$SERVER" \
    "systemctl show $SERVICE --property=MemoryCurrent" 2>/dev/null | cut -d= -f2)
  local memory_mb=$((current_memory / 1024 / 1024))
  local memory_growth=$((memory_mb - INITIAL_MEMORY / 1024 / 1024))
  
  echo "  Память: ${memory_mb}MB (рост: ${memory_growth}MB)" | tee -a "$LOG_FILE"
  
  if [ $memory_growth -gt 100 ]; then
    echo "⚠️  ВНИМАНИЕ: Память выросла на ${memory_growth}MB!" | tee -a "$LOG_FILE"
  fi
  
  # 4. Активность Event Loop
  local updates=$(ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no "$SERVER" \
    "sudo journalctl -u $SERVICE --since '1 minute ago' --no-pager 2>/dev/null | grep 'getUpdates.*200 OK' | wc -l")
  
  if [ "$updates" -gt 0 ]; then
    echo "✅ Event Loop активен ($updates запросов/мин)" | tee -a "$LOG_FILE"
  else
    echo "⚠️  Event Loop неактивен (0 запросов/мин)" | tee -a "$LOG_FILE"
  fi
  
  # 5. Ошибки за последний интервал
  local errors=$(ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no "$SERVER" \
    "sudo journalctl -u $SERVICE --since '10 minutes ago' --no-pager 2>/dev/null | grep -E '(CRITICAL|ERROR)' | wc -l")
  
  if [ "$errors" -gt 0 ]; then
    echo "⚠️  Ошибок за 10 мин: $errors" | tee -a "$LOG_FILE"
  else
    echo "✅ Ошибок нет" | tee -a "$LOG_FILE"
  fi
  
  echo "" | tee -a "$LOG_FILE"
  return 0
}

# Основной цикл тестирования
echo "🔄 Запуск мониторинга (проверка каждые 10 минут)..." | tee -a "$LOG_FILE"
echo "Нажмите Ctrl+C для остановки" | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"

iteration=1
while true; do
  if ! check_bot_health $iteration; then
    echo "❌ Тест провален! Бот упал." | tee -a "$LOG_FILE"
    break
  fi
  
  iteration=$((iteration + 1))
  
  # Проверка каждые 10 минут
  sleep 600
done

# Итоговый отчет
echo "=======================================" | tee -a "$LOG_FILE"
echo "Завершение теста: $(date)" | tee -a "$LOG_FILE"
echo "Всего проверок: $iteration" | tee -a "$LOG_FILE"
echo "Результаты сохранены в: $LOG_FILE" | tee -a "$LOG_FILE"
