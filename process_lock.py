"""
Кроссплатформенная блокировка процессов
Работает на Windows, Linux и macOS
"""

import os
import sys
import time
import logging
from typing import Optional

logger = logging.getLogger(__name__)

class ProcessLock:
    """Кроссплатформенная блокировка процесса"""
    
    def __init__(self, lock_file: str):
        self.lock_file = lock_file
        self.lock_handle = None
        self.is_locked = False
        
    def acquire(self, timeout: int = 10) -> bool:
        """Приобретает блокировку"""
        if self.is_locked:
            return True
            
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            try:
                if sys.platform == 'win32':
                    # Windows: используем файл как блокировку
                    self.lock_handle = open(self.lock_file, 'w')
                    # Пытаемся получить эксклюзивную блокировку
                    import msvcrt
                    msvcrt.locking(self.lock_handle.fileno(), msvcrt.LK_NBLCK, 1)
                    self.is_locked = True
                    logger.info(f'Блокировка приобретена: {self.lock_file}')
                    return True
                else:
                    # Unix-системы: используем fcntl
                    import fcntl
                    self.lock_handle = open(self.lock_file, 'w')
                    fcntl.flock(self.lock_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    self.is_locked = True
                    logger.info(f'Блокировка приобретена: {self.lock_file}')
                    return True
                    
            except (OSError, IOError) as e:
                if self.lock_handle:
                    try:
                        self.lock_handle.close()
                    except Exception:
                        pass
                    self.lock_handle = None
                
                # Проверяем, не умер ли процесс, создавший блокировку
                if self._is_lock_stale():
                    try:
                        os.unlink(self.lock_file)
                        logger.info(f'Удалена устаревшая блокировка: {self.lock_file}')
                        continue
                    except Exception:
                        pass
                
                time.sleep(0.1)
                continue
                
        logger.error(f'Не удалось приобрести блокировку за {timeout} секунд')
        return False
    
    def release(self):
        """Освобождает блокировку"""
        if not self.is_locked:
            return
            
        try:
            if self.lock_handle:
                if sys.platform == 'win32':
                    import msvcrt
                    msvcrt.locking(self.lock_handle.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(self.lock_handle.fileno(), fcntl.LOCK_UN)
                
                self.lock_handle.close()
                self.lock_handle = None
                
            # Удаляем файл блокировки
            try:
                os.unlink(self.lock_file)
            except Exception:
                pass
                
            self.is_locked = False
            logger.info(f'Блокировка освобождена: {self.lock_file}')
            
        except Exception as e:
            logger.error(f'Ошибка при освобождении блокировки: {e}')
    
    def _is_lock_stale(self) -> bool:
        """Проверяет, не устарела ли блокировка"""
        try:
            if not os.path.exists(self.lock_file):
                return False
                
            # Проверяем время модификации файла
            mtime = os.path.getmtime(self.lock_file)
            if time.time() - mtime > 300:  # 5 минут
                return True
                
            # На Windows проверяем, существует ли процесс с PID из файла
            if sys.platform == 'win32':
                try:
                    with open(self.lock_file, 'r') as f:
                        content = f.read().strip()
                        if content.isdigit():
                            pid = int(content)
                            # Проверяем существование процесса
                            import psutil
                            if not psutil.pid_exists(pid):
                                return True
                except Exception:
                    pass
                    
        except Exception:
            pass
            
        return False
    
    def __enter__(self):
        """Контекстный менеджер"""
        if not self.acquire():
            raise RuntimeError(f'Не удалось приобрести блокировку: {self.lock_file}')
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Контекстный менеджер"""
        self.release()

def acquire_process_lock(lock_file: str, timeout: int = 10) -> Optional[ProcessLock]:
    """Приобретает блокировку процесса"""
    lock = ProcessLock(lock_file)
    if lock.acquire(timeout):
        return lock
    return None


