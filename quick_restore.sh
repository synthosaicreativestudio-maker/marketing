#!/bin/bash

# Быстрое восстановление из последней точки отката
# Использование: ./quick_restore.sh

PROJECT_DIR="/Users/verakoroleva/Desktop/@marketing"
BACKUP_BASE_DIR="$PROJECT_DIR/rollback_points"

cd "$PROJECT_DIR" || exit 1

echo "🔄 БЫСТРОЕ ВОССТАНОВЛЕНИЕ ИЗ ПОСЛЕДНЕЙ ТОЧКИ ОТКАТА"
echo "=================================================="

# Проверяем наличие последней точки отката
if [ ! -f "$BACKUP_BASE_DIR/latest_rollback.txt" ]; then
    echo "❌ Точки отката не найдены!"
    echo "💡 Сначала создайте точку отката: ./create_rollback_point.sh"
    exit 1
fi

LATEST_ROLLBACK=$(cat "$BACKUP_BASE_DIR/latest_rollback.txt")
ROLLBACK_DIR="$BACKUP_BASE_DIR/$LATEST_ROLLBACK"

if [ ! -d "$ROLLBACK_DIR" ]; then
    echo "❌ Директория точки отката не найдена: $ROLLBACK_DIR"
    exit 1
fi

echo "📍 Найдена последняя точка отката: $LATEST_ROLLBACK"
echo "📂 Директория: $ROLLBACK_DIR"

# Подтверждение
echo ""
read -p "❓ Вы уверены, что хотите восстановить проект из этой точки отката? [y/N]: " -n 1 -r
echo ""

if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "🚫 Восстановление отменено"
    exit 0
fi

echo ""
echo "🔄 Выполняется восстановление..."

# Выполняем восстановление
if [ -f "$ROLLBACK_DIR/restore.sh" ]; then
    "$ROLLBACK_DIR/restore.sh"
else
    echo "❌ Скрипт восстановления не найден в точке отката"
    exit 1
fi