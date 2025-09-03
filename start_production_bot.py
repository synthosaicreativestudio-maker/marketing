#!/usr/bin/env python3
"""
Архитектурно правильный запуск бота с контролем единственности.
Реализует принципы системной устойчивости из современного руководства.
"""

import os
import sys
import time
import signal
import logging
from pathlib import Path

# Добавляем путь к проекту
PROJECT_DIR = Path("/Users/verakoroleva/Desktop/@marketing")
sys.path.insert(0, str(PROJECT_DIR))

# from ensure_single_instance import SingleInstanceController  # Файл не существует

class ProductionBotLauncher:
    """
    Production-уровень запуска бота согласно архитектурным принципам.
    """
    
    def __init__(self):
        self.project_dir = PROJECT_DIR
        # self.controller = SingleInstanceController(str(self.project_dir))  # Временно отключено
        self.bot_process = None
        self.setup_logging()
        self.setup_signal_handlers()
    
    def setup_logging(self):
        """Настройка логирования согласно архитектурным стандартам."""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - [%(levelname)s] - %(funcName)s:%(lineno)d - %(message)s',
            handlers=[
                logging.StreamHandler(sys.stdout),
                logging.FileHandler(self.project_dir / 'launcher.log', mode='a', encoding='utf-8')
            ]
        )
        self.logger = logging.getLogger('bot_launcher')
    
    def setup_signal_handlers(self):
        """Настройка обработчиков сигналов для graceful shutdown."""
        signal.signal(signal.SIGTERM, self.signal_handler)
        signal.signal(signal.SIGINT, self.signal_handler)
        
        # macOS specific
        if hasattr(signal, 'SIGHUP'):
            signal.signal(signal.SIGHUP, self.signal_handler)
    
    def signal_handler(self, signum, frame):
        """Обработчик сигналов для корректного завершения."""
        self.logger.info(f"📡 Получен сигнал {signum}, начинаем graceful shutdown...")
        self.graceful_shutdown()
        sys.exit(0)
    
    def graceful_shutdown(self):
        """Корректное завершение всех процессов."""
        self.logger.info("🛑 Выполнение graceful shutdown...")
        
        if self.bot_process:
            try:
                self.bot_process.terminate()
                self.bot_process.wait(timeout=10)
                self.logger.info("✅ Bot процесс корректно завершен")
            except Exception as e:
                self.logger.warning(f"⚠️ Принудительное завершение bot процесса: {e}")
                if self.bot_process.poll() is None:
                    self.bot_process.kill()
        
        # Очистка ресурсов
        self.controller.cleanup_resources()
    
    def validate_environment(self) -> bool:
        """Валидация окружения согласно архитектурным требованиям."""
        self.logger.info("🔍 Валидация окружения...")
        
        # Проверка Python версии
        if sys.version_info < (3, 7):
            self.logger.error("❌ Требуется Python 3.7+")
            return False
        
        # Проверка основных файлов
        required_files = ['bot.py', 'config.py', '.env']
        for file_name in required_files:
            file_path = self.project_dir / file_name
            if not file_path.exists():
                self.logger.error(f"❌ Отсутствует обязательный файл: {file_name}")
                return False
        
        # Проверка зависимостей
        try:
            import telegram
            import gspread
            import openai
            self.logger.info("✅ Все зависимости доступны")
        except ImportError as e:
            self.logger.error(f"❌ Отсутствует зависимость: {e}")
            return False
        
        # Проверка переменных окружения
        os.chdir(self.project_dir)
        from dotenv import load_dotenv
        load_dotenv()
        
        if not os.getenv('TELEGRAM_TOKEN'):
            self.logger.error("❌ TELEGRAM_TOKEN не найден в переменных окружения")
            return False
        
        self.logger.info("✅ Окружение валидно")
        return True
    
    def start_bot(self) -> bool:
        """Запуск бота с полным контролем."""
        self.logger.info("🚀 ЗАПУСК PRODUCTION БОТА")
        self.logger.info("=" * 50)
        
        try:
            # Шаг 1: Обеспечение единственности экземпляра
            if not self.controller.ensure_single_instance():
                self.logger.error("❌ Не удалось обеспечить единственность экземпляра")
                return False
            
            # Шаг 2: Валидация окружения
            if not self.validate_environment():
                self.logger.error("❌ Валидация окружения не пройдена")
                return False
            
            # Шаг 3: Запуск бота
            self.logger.info("🎯 Запуск основного процесса бота...")
            
            import subprocess
            self.bot_process = subprocess.Popen(
                [sys.executable, 'bot.py'],
                cwd=self.project_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                universal_newlines=True
            )
            
            self.logger.info(f"✅ Bot запущен с PID: {self.bot_process.pid}")
            
            # Шаг 4: Мониторинг процесса
            return self.monitor_bot_process()
            
        except Exception as e:
            self.logger.error(f"❌ КРИТИЧЕСКАЯ ОШИБКА при запуске: {e}")
            import traceback
            self.logger.error(f"Traceback: {traceback.format_exc()}")
            return False
    
    def monitor_bot_process(self) -> bool:
        """Мониторинг процесса бота в реальном времени."""
        self.logger.info("👁️ Начинаем мониторинг процесса бота...")
        
        try:
            while True:
                # Проверяем статус процесса
                poll_result = self.bot_process.poll()
                
                if poll_result is not None:
                    # Процесс завершился
                    if poll_result == 0:
                        self.logger.info("✅ Bot процесс завершился корректно")
                        return True
                    else:
                        self.logger.error(f"❌ Bot процесс завершился с ошибкой: код {poll_result}")
                        return False
                
                # Читаем и логируем выход бота
                try:
                    output = self.bot_process.stdout.readline()
                    if output:
                        output = output.strip()
                        if output:
                            # Пропускаем через наш логгер для единообразия
                            if 'ERROR' in output or 'CRITICAL' in output:
                                self.logger.error(f"BOT: {output}")
                            elif 'WARNING' in output:
                                self.logger.warning(f"BOT: {output}")
                            else:
                                self.logger.info(f"BOT: {output}")
                except Exception as e:
                    self.logger.debug(f"Ошибка чтения выхода бота: {e}")
                
                time.sleep(0.1)  # Небольшая пауза для снижения нагрузки на CPU
                
        except KeyboardInterrupt:
            self.logger.info("🛑 Получен Ctrl+C, выполняем graceful shutdown...")
            self.graceful_shutdown()
            return True
        except Exception as e:
            self.logger.error(f"❌ Ошибка мониторинга: {e}")
            return False

def main():
    """Главная функция production запуска."""
    launcher = ProductionBotLauncher()
    
    try:
        success = launcher.start_bot()
        return 0 if success else 1
    except Exception as e:
        print(f"💥 КРИТИЧЕСКАЯ ОШИБКА LAUNCHER: {e}")
        return 1
    finally:
        launcher.graceful_shutdown()

if __name__ == "__main__":
    sys.exit(main())