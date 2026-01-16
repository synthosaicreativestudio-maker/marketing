# Настройка Web App на PythonAnywhere для REST API

## Автоматическая настройка

### Шаг 1: Создание Web App (если еще нет)

1. В панели PythonAnywhere перейдите в **Web**
2. Нажмите **"Add a new web app"**
3. Выберите **Python 3.10**
4. Выберите **Manual configuration**
5. Нажмите **Next**

### Шаг 2: Настройка WSGI файла

1. В разделе **Code** найдите **WSGI configuration file**
2. Нажмите на ссылку для редактирования
3. Замените содержимое на:

```python
import sys
import os

# Добавляем путь к проекту
path = '/home/SynthosAI/marketing'
if path not in sys.path:
    sys.path.insert(0, path)

# Устанавливаем переменные окружения
os.environ.setdefault('DATABASE_URL', 'sqlite:///./db/appeals.db')

# Импортируем FastAPI приложение
from api.main import app

# Для PythonAnywhere WSGI
application = app
```

4. Сохраните файл

### Шаг 3: Настройка Static files для админ-панели

1. В разделе **Static files** нажмите **Add a new mapping**
2. URL: `/admin/`
3. Directory: `/home/SynthosAI/marketing/admin/`
4. Сохраните

### Шаг 4: Перезагрузка

1. Нажмите зеленую кнопку **"Reload SynthosAI.pythonanywhere.com"**

### Шаг 5: Проверка

Откройте в браузере:
- API: `https://SynthosAI.pythonanywhere.com/docs`
- Админ-панель: `https://SynthosAI.pythonanywhere.com/admin/`

---

## Альтернатива: Использование существующего Web App

Если у вас уже есть Web App (например, для webhook_handler.py), можно добавить FastAPI в тот же WSGI файл или создать отдельный endpoint.

---

**Важно:** Замените `/home/SynthosAI/marketing` на ваш реальный путь к проекту!
