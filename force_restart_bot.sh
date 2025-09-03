#!/bin/bash

# Comprehensive Bot Restart Script
# Implements the technical plan's process management requirements

BOT_DIR="/Users/verakoroleva/Desktop/@marketing"
cd "$BOT_DIR" || exit 1

echo "🔧 КОМПЛЕКСНЫЙ ПЕРЕЗАПУСК TELEGRAM БОТА"
echo "======================================"

# Step 1: Stop systemd service if running
echo "1️⃣ Остановка systemd службы..."
sudo systemctl stop marketing-bot.service 2>/dev/null || echo "   (служба не была запущена)"

# Step 2: Kill all Python bot processes
echo "2️⃣ Принудительная остановка всех процессов бота..."
pgrep -f "python.*bot.py" | while read pid; do
    echo "   Завершаем процесс $pid"
    kill -TERM "$pid" 2>/dev/null
done

# Wait for graceful shutdown
echo "   Ожидание корректного завершения (5 сек)..."
sleep 5

# Force kill any remaining processes
pgrep -f "python.*bot.py" | while read pid; do
    echo "   Принудительное завершение процесса $pid"
    kill -KILL "$pid" 2>/dev/null
done

# Step 3: Clean up lock files and cache
echo "3️⃣ Очистка временных файлов..."
rm -f "$BOT_DIR/bot.lock"
rm -f "$BOT_DIR/auth_cache.json"
rm -f "$BOT_DIR/*.pyc"
find "$BOT_DIR" -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true

# Step 4: Verify Python environment
echo "4️⃣ Проверка Python окружения..."
python3 --version
which python3

# Step 5: Check dependencies
echo "5️⃣ Проверка зависимостей..."
python3 -c "
import sys
required_modules = ['telegram', 'gspread', 'openai', 'nest_asyncio']
missing = []
for module in required_modules:
    try:
        __import__(module)
        print(f'   ✅ {module}')
    except ImportError:
        missing.append(module)
        print(f'   ❌ {module} - НЕ НАЙДЕН')

if missing:
    print(f'\\n⚠️ Недостающие модули: {missing}')
    print('Установите их: pip3 install ' + ' '.join(missing))
    sys.exit(1)
else:
    print('\\n✅ Все зависимости установлены')
"

# Step 6: Validate configuration
echo "6️⃣ Проверка конфигурации..."
if [ ! -f ".env" ] && [ ! -f "bot.env" ]; then
    echo "   ❌ Файл .env или bot.env не найден"
    exit 1
fi

if [ ! -f "credentials.json" ]; then
    echo "   ❌ Файл credentials.json не найден"
    exit 1
fi

echo "   ✅ Конфигурационные файлы найдены"

# Step 7: Start the bot with enhanced logging
echo "7️⃣ Запуск бота с обновленным кодом..."
echo "   Логи будут записываться в bot.log"
echo "   Для остановки используйте Ctrl+C"
echo ""

# Create a new terminal session for the bot
python3 bot.py 2>&1 | tee -a restart.log &
BOT_PID=$!

echo "✅ Бот запущен с PID: $BOT_PID"
echo "📋 Мониторинг логов:"
echo "   tail -f bot.log          # Основные логи"
echo "   tail -f restart.log      # Логи перезапуска"

# Monitor for the first few seconds
sleep 3
if kill -0 "$BOT_PID" 2>/dev/null; then
    echo "✅ Бот успешно запущен и работает"
    echo "🔍 Проверяем первые логи..."
    tail -10 bot.log 2>/dev/null || echo "   (логи пока не созданы)"
else
    echo "❌ Бот не запустился или завершился с ошибкой"
    echo "🔍 Проверьте логи:"
    tail -20 restart.log 2>/dev/null
    exit 1
fi

echo ""
echo "🚀 ПЕРЕЗАПУСК ЗАВЕРШЕН"
echo "========================"
echo "Для мониторинга используйте:"
echo "  ./manage_bot.sh status"
echo "  ./manage_bot.sh logs"
echo "  ./manage_bot.sh follow"