#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Скрипт управления ботом для масштабирования до 10K+ сотрудников.
Обеспечивает безопасный запуск, остановку и мониторинг бота.
"""

import os
import sys
import time
import signal
import subprocess
import psutil
import argparse
from pathlib import Path

# Добавляем текущую директорию в PATH для импорта модулей
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def get_bot_processes():
    """Возвращает список процессов бота."""
    processes = []
    for proc in psutil.process_iter(['pid', 'cmdline', 'create_time']):
        try:
            cmdline = ' '.join(proc.info['cmdline'] or [])
            if 'python' in cmdline and 'bot.py' in cmdline:
                processes.append({
                    'pid': proc.info['pid'],
                    'cmdline': cmdline,
                    'create_time': proc.info['create_time']
                })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return processes

def stop_bot(force=False):
    """Останавливает бота."""
    processes = get_bot_processes()
    
    if not processes:
        print("🤖 Бот не запущен")
        return True
    
    print(f"🔍 Найдено {len(processes)} процессов бота:")
    for proc in processes:
        print(f"   PID {proc['pid']}: {proc['cmdline']}")
    
    if not force:
        response = input("❓ Остановить все процессы? (y/N): ")
        if response.lower() not in ['y', 'yes', 'да']:
            print("❌ Отменено")
            return False
    
    # Сначала пробуем мягкое завершение
    print("🔄 Отправляю SIGTERM...")
    for proc in processes:
        try:
            os.kill(proc['pid'], signal.SIGTERM)
        except (OSError, ProcessLookupError):
            pass
    
    time.sleep(3)
    
    # Проверяем что процессы завершились
    remaining = get_bot_processes()
    if remaining:
        print("💥 Принудительно завершаю оставшиеся процессы...")
        for proc in remaining:
            try:
                os.kill(proc['pid'], signal.SIGKILL)
            except (OSError, ProcessLookupError):
                pass
        time.sleep(1)
    
    final_check = get_bot_processes()
    if final_check:
        print(f"❌ Не удалось завершить {len(final_check)} процессов")
        return False
    else:
        print("✅ Все процессы бота остановлены")
        return True

def start_bot(force=False):
    """Запускает бота."""
    # Проверяем существующие процессы
    existing = get_bot_processes()
    if existing:
        if force:
            print("🔄 Принудительный перезапуск...")
            if not stop_bot(force=True):
                print("❌ Не удалось остановить существующие процессы")
                return False
        else:
            print("❌ Бот уже запущен!")
            print("💡 Используйте --force для принудительного перезапуска")
            print("💡 Или сначала остановите: python3 manage_bot.py stop")
            return False
    
    # Проверяем файлы
    if not os.path.exists('bot.py'):
        print("❌ bot.py не найден!")
        return False
    
    if not os.path.exists('.env') and not os.path.exists('bot.env'):
        print("❌ Файл конфигурации (.env или bot.env) не найден!")
        return False
    
    print("🚀 Запускаю бота...")
    
    # Запускаем бота в фоновом режиме
    args = ['python3', 'bot.py']
    if force:
        args.append('--force')
    
    try:
        with open('bot.log', 'w') as log_file:
            process = subprocess.Popen(
                args,
                stdout=log_file,
                stderr=subprocess.STDOUT,
                start_new_session=True
            )
        
        # Даем время на запуск
        time.sleep(3)
        
        # Проверяем что процесс запущен
        if process.poll() is None:
            print(f"✅ Бот запущен с PID {process.pid}")
            print("📋 Логи: tail -f bot.log")
            return True
        else:
            print("❌ Бот завершился сразу после запуска")
            print("📋 Проверьте логи: cat bot.log")
            return False
            
    except Exception as e:
        print(f"❌ Ошибка запуска: {e}")
        return False

def status_bot():
    """Показывает статус бота."""
    processes = get_bot_processes()
    
    if not processes:
        print("🤖 Статус: ОСТАНОВЛЕН")
        return
    
    print(f"🤖 Статус: ЗАПУЩЕН ({len(processes)} процессов)")
    print("\n📊 Детали процессов:")
    
    for proc in processes:
        pid = proc['pid']
        create_time = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(proc['create_time']))
        
        try:
            process = psutil.Process(pid)
            memory_mb = process.memory_info().rss / 1024 / 1024
            cpu_percent = process.cpu_percent()
            
            print(f"   PID {pid}:")
            print(f"     Запущен: {create_time}")
            print(f"     Память: {memory_mb:.1f} MB")
            print(f"     CPU: {cpu_percent:.1f}%")
            
        except psutil.NoSuchProcess:
            print(f"   PID {pid}: процесс завершен")

def logs_bot(follow=False, lines=50):
    """Показывает логи бота."""
    if not os.path.exists('bot.log'):
        print("❌ Файл логов bot.log не найден")
        return
    
    if follow:
        print("📋 Слежение за логами (Ctrl+C для выхода):")
        try:
            subprocess.run(['tail', '-f', 'bot.log'])
        except KeyboardInterrupt:
            print("\n👋 Слежение остановлено")
    else:
        print(f"📋 Последние {lines} строк логов:")
        subprocess.run(['tail', '-n', str(lines), 'bot.log'])

def restart_bot(force=False):
    """Перезапускает бота."""
    print("🔄 Перезапуск бота...")
    
    if stop_bot(force=True):
        time.sleep(2)
        return start_bot(force=force)
    else:
        print("❌ Не удалось остановить бот для перезапуска")
        return False

def health_check():
    """Проверяет здоровье бота."""
    print("🏥 Проверка здоровья бота...\n")
    
    # Проверяем процессы
    processes = get_bot_processes()
    if not processes:
        print("❌ Бот не запущен")
        return False
    
    print(f"✅ Процессы: {len(processes)} активных")
    
    # Проверяем файлы
    required_files = ['bot.py', 'config.py', 'credentials.json']
    missing_files = [f for f in required_files if not os.path.exists(f)]
    
    if missing_files:
        print(f"❌ Отсутствуют файлы: {missing_files}")
        return False
    else:
        print("✅ Все файлы на месте")
    
    # Проверяем логи на ошибки
    if os.path.exists('bot.log'):
        try:
            with open('bot.log', 'r', encoding='utf-8') as f:
                recent_logs = f.readlines()[-100:]  # Последние 100 строк
            
            error_count = sum(1 for line in recent_logs if 'ERROR' in line or 'CRITICAL' in line)
            warning_count = sum(1 for line in recent_logs if 'WARNING' in line)
            
            if error_count > 5:
                print(f"⚠️  Много ошибок в логах: {error_count}")
                return False
            elif error_count > 0:
                print(f"⚠️  Есть ошибки в логах: {error_count}")
            else:
                print("✅ Логи чистые")
                
            if warning_count > 10:
                print(f"⚠️  Много предупреждений: {warning_count}")
            
        except Exception as e:
            print(f"❌ Не удалось проверить логи: {e}")
            return False
    
    print("\n🎉 Бот работает нормально!")
    return True

def main():
    parser = argparse.ArgumentParser(description='Управление Marketing Bot')
    subparsers = parser.add_subparsers(dest='command', help='Команды')
    
    # Команда start
    start_parser = subparsers.add_parser('start', help='Запустить бота')
    start_parser.add_argument('--force', action='store_true', help='Принудительный запуск')
    
    # Команда stop
    stop_parser = subparsers.add_parser('stop', help='Остановить бота')
    stop_parser.add_argument('--force', action='store_true', help='Принудительная остановка')
    
    # Команда restart
    restart_parser = subparsers.add_parser('restart', help='Перезапустить бота')
    restart_parser.add_argument('--force', action='store_true', help='Принудительный перезапуск')
    
    # Команда status
    subparsers.add_parser('status', help='Показать статус бота')
    
    # Команда logs
    logs_parser = subparsers.add_parser('logs', help='Показать логи')
    logs_parser.add_argument('-f', '--follow', action='store_true', help='Следить за логами')
    logs_parser.add_argument('-n', '--lines', type=int, default=50, help='Количество строк')
    
    # Команда health
    subparsers.add_parser('health', help='Проверить здоровье бота')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    # Выполняем команды
    try:
        if args.command == 'start':
            success = start_bot(force=args.force)
            sys.exit(0 if success else 1)
            
        elif args.command == 'stop':
            success = stop_bot(force=args.force)
            sys.exit(0 if success else 1)
            
        elif args.command == 'restart':
            success = restart_bot(force=args.force)
            sys.exit(0 if success else 1)
            
        elif args.command == 'status':
            status_bot()
            
        elif args.command == 'logs':
            logs_bot(follow=args.follow, lines=args.lines)
            
        elif args.command == 'health':
            success = health_check()
            sys.exit(0 if success else 1)
            
    except KeyboardInterrupt:
        print("\n👋 Прервано пользователем")
        sys.exit(130)
    except Exception as e:
        print(f"❌ Неожиданная ошибка: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()