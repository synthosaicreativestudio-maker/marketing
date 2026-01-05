"""
WSGI файл для запуска FastAPI на PythonAnywhere.
FastAPI требует ASGI, поэтому используем адаптер.
"""
import sys
import os

# Добавляем путь к проекту
path = '/home/SynthosAI/marketing'
if path not in sys.path:
    sys.path.insert(0, path)

# Устанавливаем переменные окружения
os.environ.setdefault('DATABASE_URL', 'sqlite:///./db/appeals.db')

# Меняем рабочую директорию на папку проекта
os.chdir(path)

try:
    # Импортируем FastAPI приложение
    from api.main import app
    
    # Используем ASGI-to-WSGI адаптер
    from asgiref.wsgi import WsgiToAsgi
    
    # Обертываем FastAPI app в WSGI адаптер
    application = WsgiToAsgi(app)
    
except ImportError as e:
    # Если адаптер не установлен, используем простой вариант
    # Установите: pip3.10 install --user asgiref
    def application(environ, start_response):
        start_response('500 Internal Server Error', [('Content-Type', 'text/plain')])
        return [f'Error: {str(e)}\nPlease install asgiref: pip3.10 install --user asgiref'.encode()]
