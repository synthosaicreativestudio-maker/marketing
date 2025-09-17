#!/usr/bin/env python3
"""Простой HTTP сервер для раздачи статических файлов WebApp"""
import http.server
import socketserver
import os
import logging
from pathlib import Path

# Настройка логирования
logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

class WebAppHandler(http.server.SimpleHTTPRequestHandler):
    """Обработчик для статических файлов WebApp"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory="webapp", **kwargs)
    
    def end_headers(self):
        # Добавляем CORS заголовки для Telegram WebApp
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        super().end_headers()
    
    def log_message(self, format, *args):
        log.info(f"{self.address_string()} - {format % args}")

def main():
    """Запуск веб-сервера"""
    port = int(os.environ.get('PORT', 8080))
    
    # Проверяем наличие папки webapp
    webapp_dir = Path('webapp')
    if not webapp_dir.exists():
        log.error("❌ Папка webapp не найдена!")
        return 1
    
    if not (webapp_dir / 'index.html').exists():
        log.error("❌ Файл webapp/index.html не найден!")
        return 1
    
    try:
        with socketserver.TCPServer(("", port), WebAppHandler) as httpd:
            log.info(f"🌐 WebApp сервер запущен на порту {port}")
            log.info(f"📱 Доступ: http://localhost:{port}/")
            log.info(f"📁 Раздача файлов из: {webapp_dir.absolute()}")
            httpd.serve_forever()
    except KeyboardInterrupt:
        log.info("🛑 Сервер остановлен")
    except Exception as e:
        log.error(f"❌ Ошибка сервера: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())
