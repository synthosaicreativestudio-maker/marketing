#!/bin/bash
# Проверка политики засыпания VM на Yandex Cloud

SSH_KEY="$HOME/.ssh/ssh-key-1767684261599/ssh-key-1767684261599"
SERVER="ubuntu@158.160.0.127"

echo "🖥️  ПРОВЕРКА ПОЛИТИКИ ЗАСЫПАНИЯ VM"
echo "===================================="
echo ""

echo "1️⃣ Проверка планировщика задач (cron):"
echo "  Ищем автоматические остановки/перезагрузки..."
CRON_JOBS=$(ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no "$SERVER" \
  "crontab -l 2>/dev/null; sudo crontab -l 2>/dev/null" | grep -E "(shutdown|poweroff|reboot|suspend)")

if [ -z "$CRON_JOBS" ]; then
  echo "  ✅ Автоматических задач на остановку НЕ НАЙДЕНО"
else
  echo "  ⚠️  Найдены задачи:"
  echo "$CRON_JOBS"
fi
echo ""

echo "2️⃣ Проверка systemd таймеров:"
TIMERS=$(ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no "$SERVER" \
  "systemctl list-timers --all --no-pager" | grep -E "(shutdown|poweroff|suspend)")

if [ -z "$TIMERS" ]; then
  echo "  ✅ Таймеров на остановку НЕ НАЙДЕНО"
else
  echo "  ⚠️  Найдены таймеры:"
  echo "$TIMERS"
fi
echo ""

echo "3️⃣ Проверка uptime VM:"
UPTIME=$(ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no "$SERVER" "uptime -p")
echo "  VM работает: $UPTIME"
echo ""

echo "4️⃣ Проверка последних перезагрузок:"
LAST_BOOTS=$(ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no "$SERVER" \
  "last reboot -n 5 2>/dev/null")
echo "$LAST_BOOTS"
echo ""

echo "5️⃣ Проверка политики питания:"
POWER_POLICY=$(ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no "$SERVER" \
  "cat /sys/power/state 2>/dev/null || echo 'Не поддерживается на VM'")
echo "  Режимы питания: $POWER_POLICY"
echo ""

echo "6️⃣ Проверка запланированных выключений в systemd:"
SHUTDOWN_SCHEDULE=$(ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no "$SERVER" \
  "systemctl status systemd-shutdownd 2>/dev/null || echo 'Не запланировано'")
echo "  $SHUTDOWN_SCHEDULE"
echo ""

echo "===================================="
echo "📋 ИТОГ:"
echo ""
echo "Yandex Cloud VM обычно НЕ имеют автоматического засыпания."
echo "VM работает 24/7 пока не остановлена вручную или через API."
echo ""
echo "Если бот 'засыпает', причины обычно:"
echo "  - Падение процесса бота (systemd перезапустит автоматически)"
echo "  - Проблемы с сетью/интернетом на VM"
echo "  - Ручная остановка через Yandex Console"
echo "  - Превышение квот/биллинга"
echo ""
echo "Для мониторинга используйте:"
echo "  bash scripts/long_term_stability_test.sh"
