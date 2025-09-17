# 🌐 Развертывание WebApp

## 📋 Обзор

WebApp состоит из статических файлов (`index.html`, `app.js`) которые нужно разместить на веб-сервере, доступном из интернета.

## 🚀 Варианты развертывания

### 1. GitHub Pages (Рекомендуется)

**Преимущества:** Бесплатно, автоматическое развертывание, HTTPS

**Шаги:**
1. Создайте отдельный репозиторий для WebApp или используйте ветку `gh-pages`
2. Скопируйте файлы из папки `webapp/` в корень репозитория
3. Включите GitHub Pages в настройках репозитория
4. Используйте URL: `https://username.github.io/repository-name/`

**Пример структуры репозитория:**
```
your-webapp-repo/
├── index.html    # Скопировать из webapp/index.html
├── app.js        # Скопировать из webapp/app.js
└── README.md     # Описание WebApp
```

### 2. Netlify

**Преимущества:** Простое развертывание, автоматические сборки

**Шаги:**
1. Зарегистрируйтесь на [netlify.com](https://netlify.com)
2. Подключите GitHub репозиторий с файлами WebApp
3. Настройте автоматическое развертывание
4. Получите URL: `https://your-app.netlify.app/`

### 3. Vercel

**Преимущества:** Быстрое развертывание, хорошая производительность

**Шаги:**
1. Зарегистрируйтесь на [vercel.com](https://vercel.com)
2. Импортируйте проект из GitHub
3. Настройте папку `webapp/` как корневую
4. Получите URL: `https://your-app.vercel.app/`

### 4. Собственный сервер

**Для продакшена с Docker:**

```bash
# Запуск только WebApp сервера
docker-compose up webapp

# Или запуск всех сервисов
docker-compose up -d
```

**Настройка переменных:**
```env
WEBAPP_URL=https://your-domain.com
WEBAPP_PORT=8080
```

## ⚙️ Настройка бота

После развертывания WebApp обновите переменную окружения:

```env
WEBAPP_URL=https://your-deployed-webapp-url.com
```

**Примеры URL:**
- GitHub Pages: `https://username.github.io/webapp-repo`
- Netlify: `https://your-app.netlify.app`
- Vercel: `https://your-app.vercel.app`
- Собственный сервер: `https://your-domain.com`

## 🧪 Тестирование

### Локальное тестирование

```bash
# Запуск локального сервера
python server.py

# Или через Docker
docker-compose up webapp
```

Откройте: `http://localhost:8080`

### Проверка интеграции

1. **Проверьте доступность WebApp** по URL
2. **Убедитесь, что файлы загружаются** без ошибок 404
3. **Протестируйте в Telegram** с реальным ботом
4. **Проверьте отправку данных** через WebApp

## 🔧 Отладка

### Частые проблемы

**1. Ошибка 404 для app.js**
- ✅ Проверьте путь в `index.html`: `<script src="app.js"></script>`
- ❌ Неправильно: `<script src="/webapp/app.js"></script>`

**2. CORS ошибки**
- Убедитесь, что сервер отдает правильные CORS заголовки
- Для GitHub Pages это работает автоматически

**3. Telegram WebApp не инициализируется**
- Проверьте загрузку скрипта: `https://telegram.org/js/telegram-web-app.js`
- Убедитесь, что WebApp открывается из Telegram

### Логи и отладка

**В браузере (F12 → Console):**
```javascript
// Проверка инициализации
console.log('Telegram WebApp:', window.Telegram?.WebApp);

// Проверка отправки данных
window.Telegram.WebApp.sendData('{"test": "data"}');
```

**В боте:**
```python
# Включите отладочные логи
LOG_LEVEL=DEBUG
```

## 📚 Дополнительные ресурсы

- [Telegram WebApp API](https://core.telegram.org/bots/webapps)
- [GitHub Pages документация](https://pages.github.com/)
- [Netlify документация](https://docs.netlify.com/)
- [Vercel документация](https://vercel.com/docs)
