# -*- coding: utf-8 -*-
"""
Менеджер процессов для предотвращения запуска множественных экземпляров бота.
Критически важно для масштабирования до 10K+ сотрудников.
"""

import os
import sys
import time
import signal
import logging
import fcntl
import atexit
import psutil
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

class ProcessManager:
    """
    Менеджер для контроля единственности экземпляра бота.
    Использует файловые блокировки и PID файлы.
    """
    
    def __init__(self, name: str = "telegram_bot"):
        self.name = name
        self.pid_file = Path(f"/tmp/{name}.pid")
        self.lock_file = Path(f"/tmp/{name}.lock")
        self.lock_fd = None
        
    def is_running(self) -> bool:
        """Проверяет, запущен ли уже процесс."""
        if not self.pid_file.exists():
            return False
            
        try:
            with open(self.pid_file, 'r') as f:
                pid = int(f.read().strip())
            
            # Проверяем, существует ли процесс
            if psutil.pid_exists(pid):
                # Проверяем, что это действительно наш процесс
                process = psutil.Process(pid)
                cmdline = ' '.join(process.cmdline())
                if 'bot.py' in cmdline:
                    return True
            
            # Если процесс не существует, удаляем старый PID файл
            self.pid_file.unlink()
            return False
            
        except (ValueError, psutil.NoSuchProcess, psutil.AccessDenied):
            # Если не можем прочитать PID или процесс не существует
            if self.pid_file.exists():
                self.pid_file.unlink()
            return False
    
    def acquire_lock(self) -> bool:
        """Получает эксклюзивную блокировку."""
        try:
            self.lock_fd = open(self.lock_file, 'w')
            fcntl.flock(self.lock_fd.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            
            # Записываем PID
            pid = os.getpid()
            with open(self.pid_file, 'w') as f:
                f.write(str(pid))
            
            # Регистрируем очистку при выходе
            atexit.register(self.release_lock)
            signal.signal(signal.SIGTERM, self._signal_handler)
            signal.signal(signal.SIGINT, self._signal_handler)
            
            logger.info(f"✅ Блокировка получена, PID: {pid}")
            return True
            
        except (IOError, OSError) as e:
            logger.error(f"❌ Не удалось получить блокировку: {e}")
            return False
    
    def release_lock(self):
        """Освобождает блокировку и очищает файлы."""
        try:
            if self.lock_fd:
                fcntl.flock(self.lock_fd.fileno(), fcntl.LOCK_UN)
                self.lock_fd.close()
                self.lock_fd = None
            
            if self.lock_file.exists():
                self.lock_file.unlink()
                
            if self.pid_file.exists():
                self.pid_file.unlink()
                
            logger.info("🔓 Блокировка освобождена")
            
        except Exception as e:
            logger.error(f"Ошибка при освобождении блокировки: {e}")
    
    def _signal_handler(self, signum, frame):
        """Обработчик сигналов для корректного завершения."""
        logger.info(f"📡 Получен сигнал {signum}, завершаем работу...")
        self.release_lock()
        sys.exit(0)
    
    def kill_existing_instances(self) -> int:
        """
        Убивает все существующие экземпляры бота.
        Возвращает количество завершенных процессов.
        """
        killed_count = 0
        
        try:
            for process in psutil.process_iter(['pid', 'cmdline']):
                try:
                    cmdline = ' '.join(process.info['cmdline'] or [])
                    if 'python' in cmdline and 'bot.py' in cmdline:
                        pid = process.info['pid']
                        if pid != os.getpid():  # Не убиваем себя
                            logger.info(f"🔥 Завершаю процесс: PID {pid}")
                            process.terminate()
                            
                            # Ждем немного и убиваем принудительно если нужно
                            try:
                                process.wait(timeout=5)
                            except psutil.TimeoutExpired:
                                process.kill()
                                
                            killed_count += 1
                            
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
                    
        except Exception as e:
            logger.error(f"Ошибка при завершении процессов: {e}")
        
        if killed_count > 0:
            logger.info(f"✅ Завершено {killed_count} экземпляров бота")
            time.sleep(2)  # Даем время на завершение
            
        return killed_count


class BotInstanceManager:
    """
    Высокоуровневый менеджер для управления экземплярами бота.
    Предназначен для масштабирования до 10K+ пользователей.
    """
    
    def __init__(self):
        self.process_manager = ProcessManager()
        
    def ensure_single_instance(self, force_restart: bool = False) -> bool:
        """
        Гарантирует запуск только одного экземпляра бота.
        
        Args:
            force_restart: Принудительно завершить существующие экземпляры
            
        Returns:
            True если можно продолжать запуск, False если нужно завершиться
        """
        
        # Проверяем существующие экземпляры
        if self.process_manager.is_running():
            if force_restart:
                logger.warning("🔄 Принудительный перезапуск: завершаю существующие экземпляры")
                self.process_manager.kill_existing_instances()
            else:
                logger.error("❌ Экземпляр бота уже запущен!")
                logger.error("💡 Используйте --force для принудительного перезапуска")
                logger.error("💡 Или выполните: pkill -f 'python.*bot.py'")
                return False
        
        # Убиваем все возможные дублирующие процессы
        killed = self.process_manager.kill_existing_instances()
        if killed > 0:
            logger.info(f"🧹 Очищено {killed} старых экземпляров")
        
        # Получаем блокировку
        if not self.process_manager.acquire_lock():
            logger.error("❌ Не удалось получить эксклюзивную блокировку")
            return False
            
        logger.info("🚀 Готов к запуску единственного экземпляра бота")
        return True
    
    def cleanup(self):
        """Очистка ресурсов."""
        self.process_manager.release_lock()


# Глобальный экземпляр менеджера
instance_manager = BotInstanceManager()

def ensure_single_bot_instance(force_restart: bool = False) -> bool:
    """
    Удобная функция для проверки единственности экземпляра.
    
    Пример использования:
        if not ensure_single_bot_instance():
            sys.exit(1)
    """
    return instance_manager.ensure_single_instance(force_restart)

def cleanup_bot_instance():
    """Очистка при завершении."""
    instance_manager.cleanup()