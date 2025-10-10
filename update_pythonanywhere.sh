#!/bin/bash

# Скрипт для обновления бота на PythonAnywhere
echo "🚀 Обновление MarketingBot на PythonAnywhere..."

# Переходим в папку проекта
cd ~/marketing

# Останавливаем текущий бот
echo "⏹️ Остановка текущего бота..."
pkill -f "python.*bot" || echo "Бот не был запущен"

# Обновляем код из GitHub
echo "📥 Обновление кода из GitHub..."
git fetch origin
git pull origin main

# Обновляем зависимости
echo "📦 Обновление зависимостей..."
pip3.10 install --user -r requirements.txt

# Запускаем бота
echo "▶️ Запуск обновленного бота..."
nohup python3.10 bot.py > bot.log 2>&1 &

echo "✅ Обновление завершено!"
echo "📋 Проверьте логи: tail -f bot.log"
echo "🔍 Статус процесса: ps aux | grep python"
