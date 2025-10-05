# 🧪 Тестирование MarketingBot v3.1

## Обзор тестирования

MarketingBot v3.1 включает комплексную систему тестирования для всех компонентов:
- **Unit tests**: тестирование отдельных функций и модулей
- **Integration tests**: тестирование взаимодействия компонентов
- **E2E tests**: симуляция рабочих сценариев
- **Manual tests**: ручное тестирование новых функций

## Новые тесты для v3.1

### 1. Тестирование автоматической эскалации

```python
# test_escalation.py
import pytest
from handlers import _is_user_escalation_request

def test_escalation_detection():
    """Тест определения запросов эскалации"""
    
    # Положительные случаи
    escalation_phrases = [
        "а вы мне помочь не можете?",
        "не можете помочь",
        "специалист нужен",
        "нужен специалист", 
        "человек нужен",
        "живой человек нужен",
        "соедините с человеком",
        "позвонить хочу",
        "проблема у меня",
        "не получается",
        "не работает",
        "сложно разобраться",
        "не понимаю",
        "объясните подробнее"
    ]
    
    for phrase in escalation_phrases:
        assert _is_user_escalation_request(phrase), f"Фраза '{phrase}' должна определяться как эскалация"
    
    # Отрицательные случаи
    normal_phrases = [
        "привет",
        "как дела",
        "спасибо",
        "вопрос по маркетингу",
        "расскажите о продукте"
    ]
    
    for phrase in normal_phrases:
        assert not _is_user_escalation_request(phrase), f"Фраза '{phrase}' НЕ должна определяться как эскалация"

def test_escalation_case_insensitive():
    """Тест регистронезависимости"""
    assert _is_user_escalation_request("СПЕЦИАЛИСТ НУЖЕН")
    assert _is_user_escalation_request("Специалист Нужен")
    assert _is_user_escalation_request("специалист нужен")
```

### 2. Тестирование обновления статусов

```python
# test_status_updates.py
import pytest
from appeals_service import AppealsService
from unittest.mock import Mock, patch

def test_status_update_to_in_work():
    """Тест обновления статуса на 'в работе'"""
    appeals_service = AppealsService()
    
    with patch.object(appeals_service, 'set_status_in_work') as mock_set_status:
        mock_set_status.return_value = True
        
        result = appeals_service.set_status_in_work(123456789)
        
        assert result is True
        mock_set_status.assert_called_once_with(123456789)

def test_status_update_to_resolved():
    """Тест обновления статуса на 'решено'"""
    appeals_service = AppealsService()
    
    with patch.object(appeals_service.worksheet, 'batch_update') as mock_batch:
        mock_batch.return_value = {}
        
        # Симуляция обновления статуса
        appeals_service.worksheet.batch_update([{
            'range': 'F3',
            'values': [['решено']]
        }])
        
        mock_batch.assert_called_once()

def test_background_color_removal():
    """Тест удаления красной заливки"""
    appeals_service = AppealsService()
    
    with patch.object(appeals_service.worksheet, 'format') as mock_format:
        # Симуляция удаления заливки
        appeals_service.worksheet.format('F3', {
            "backgroundColor": {
                "red": 1.0,
                "green": 1.0, 
                "blue": 1.0
            }
        })
        
        mock_format.assert_called_once()
```

### 3. Тестирование WebApp URL генерации

```python
# test_webapp_urls.py
import pytest
from handlers import get_web_app_url, get_spa_menu_url
from unittest.mock import patch

def test_webapp_url_generation():
    """Тест генерации URL для WebApp"""
    
    with patch.dict('os.environ', {'WEB_APP_URL': 'https://example.com'}):
        auth_url = get_web_app_url()
        menu_url = get_spa_menu_url()
        
        assert auth_url == 'https://example.com/'
        assert menu_url == 'https://example.com/personal.html'

def test_webapp_url_without_trailing_slash():
    """Тест URL без завершающего слеша"""
    
    with patch.dict('os.environ', {'WEB_APP_URL': 'https://example.com'}):
        auth_url = get_web_app_url()
        menu_url = get_spa_menu_url()
        
        assert auth_url == 'https://example.com/'
        assert menu_url == 'https://example.com/personal.html'

def test_webapp_url_with_trailing_slash():
    """Тест URL с завершающим слешем"""
    
    with patch.dict('os.environ', {'WEB_APP_URL': 'https://example.com/'}):
        auth_url = get_web_app_url()
        menu_url = get_spa_menu_url()
        
        assert auth_url == 'https://example.com/'
        assert menu_url == 'https://example.com/personal.html'
```

### 4. Тестирование ResponseMonitor

```python
# test_response_monitor.py
import pytest
from response_monitor import ResponseMonitor
from unittest.mock import Mock, patch, AsyncMock

@pytest.mark.asyncio
async def test_response_sending():
    """Тест отправки ответов специалистов"""
    
    mock_bot = Mock()
    mock_appeals_service = Mock()
    mock_appeals_service.check_for_responses.return_value = [
        {
            'row': 3,
            'telegram_id': '123456789',
            'response': 'Ответ специалиста',
            'code': '111098',
            'fio': 'Тестовый Пользователь'
        }
    ]
    
    monitor = ResponseMonitor(mock_bot, mock_appeals_service)
    
    with patch.object(monitor, '_send_response', new_callable=AsyncMock) as mock_send:
        await monitor.check_responses()
        
        mock_send.assert_called_once()

@pytest.mark.asyncio
async def test_status_update_after_response():
    """Тест обновления статуса после отправки ответа"""
    
    mock_bot = Mock()
    mock_appeals_service = Mock()
    mock_appeals_service.worksheet = Mock()
    
    monitor = ResponseMonitor(mock_bot, mock_appeals_service)
    
    response_data = {
        'row': 3,
        'telegram_id': '123456789',
        'response': 'Ответ специалиста'
    }
    
    with patch.object(monitor.appeals_service.worksheet, 'batch_update') as mock_batch:
        with patch.object(monitor.appeals_service.worksheet, 'format') as mock_format:
            await monitor._send_response(response_data)
            
            # Проверяем обновление статуса
            mock_batch.assert_called()
            # Проверяем удаление заливки
            mock_format.assert_called()
```

## Ручное тестирование

### 1. Тест автоматической эскалации

```bash
# Запуск бота
python3 bot.py

# В Telegram отправьте сообщения:
# "а вы мне помочь не можете?" - должно сработать эскалация
# "нужен специалист" - должно сработать эскалация  
# "привет" - НЕ должно сработать эскалация
```

### 2. Тест обновления статусов

```bash
# 1. Создайте обращение через бота
# 2. В Google Sheets добавьте ответ специалиста в колонку G
# 3. Проверьте, что:
#    - Ответ отправился пользователю
#    - Статус изменился на "решено"
#    - Красная заливка удалилась
```

### 3. Тест WebApp кнопок

```bash
# 1. Авторизуйтесь через WebApp
# 2. Проверьте, что показывается кнопка "Меню" (не "Авторизоваться")
# 3. Нажмите на кнопку меню
# 4. Проверьте, что открывается personal.html
```

## Запуск тестов

```bash
# Установка зависимостей для тестирования
pip install pytest pytest-asyncio

# Запуск всех тестов
pytest

# Запуск конкретного теста
pytest test_escalation.py

# Запуск с подробным выводом
pytest -v

# Запуск с покрытием
pytest --cov=.
```

## CI/CD тестирование

```yaml
# .github/workflows/test.yml
name: Tests
on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v2
    - name: Set up Python
      uses: actions/setup-python@v2
      with:
        python-version: 3.8
    - name: Install dependencies
      run: |
        pip install -r requirements.txt
        pip install pytest pytest-asyncio
    - name: Run tests
      run: pytest
```

## Отчеты о тестировании

```bash
# Генерация HTML отчета
pytest --html=report.html --self-contained-html

# Генерация XML отчета для CI
pytest --junitxml=report.xml

# Покрытие кода
pytest --cov=. --cov-report=html
```

## Мониторинг тестов

```bash
# Непрерывное тестирование при изменениях
pytest-watch

# Тестирование с профилированием
pytest --profile

# Тестирование производительности
pytest --benchmark-only
```

Local helper scripts

There are three helper scripts in `scripts/` to help testing the WebApp auth flow locally:

- `scripts/generate_initdata.py` — generate a signed Telegram WebApp `initData` (HMAC using SHA256(bot_token)).
- `scripts/test_auth_via_bot.py` — convenience script that generates `initData` and POSTs to `http://127.0.0.1:8000/api/webapp/auth`.
- `scripts/send_webapp_button.py` — sends an inline keyboard with a Web App button to a chat (requires `BOT_TOKEN` env var).

Examples:

```
# generate initData
python scripts/generate_initdata.py --bot-token $BOT_TOKEN --user-id 123456

# run local test (will POST to local server)
export BOT_TOKEN=...
python scripts/test_auth_via_bot.py --user-id 123456 --partner-code 111098 --phone "+7 982 770-1055"

# send webapp button (after running ngrok and replacing URL)
python scripts/send_webapp_button.py --chat-id 123456 --url https://abcd-12.ngrok.io/webapp/index.html
```

Note: these helpers require `requests` installed in your virtualenv.

Ngrok & webhook notes

If you want Telegram to open your local Web App and forward `initData` automatically, expose your local server with ngrok:

```
.venv312/bin/uvicorn app.main:app --reload --port 8000
ngrok http 8000
```

Then set the webhook (optional) or send an inline Web App button that points to the ngrok URL. You can set webhook with:

```
export BOT_TOKEN=...
python scripts/setup_webhook.py --url https://abcd-12.ngrok.io/
```

Or send a button directly (no webhook needed) using `scripts/send_webapp_button.py`.

Restart script note

The `scripts/restart_bot.sh` script now checks for `TELEGRAM_BOT_TOKEN` (used by the app) and will warn if it's missing. Ensure your `.env` or environment uses that variable name.
