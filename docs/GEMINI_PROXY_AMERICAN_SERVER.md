# Вариант Б: обход блокировок Gemini через американский сервер

Бот на Yandex VM (Россия) обращается к Gemini API только через **обратный прокси на американском сервере**. Telegram и Google Sheets идут напрямую, без прокси.

## Схема

```
Yandex VM (ru-central1-b)  →  американский сервер (reverse proxy)  →  generativelanguage.googleapis.com
         PROXYAPI_BASE_URL                    :порт
```

- **Не трогаем:** VPN и всё, что с ним связано на американском сервере.
- **Настраиваем:** отдельный reverse proxy только для Gemini (nginx или аналог).

## 1. На американском сервере: reverse proxy для Gemini

Поднять прокси, который принимает запросы на свой порт и пересылает их на `https://generativelanguage.googleapis.com`, сохраняя путь и заголовки.

### Вариант с nginx

Установка (если ещё нет):

```bash
sudo apt update && sudo apt install -y nginx
```

Конфиг для Gemini (например `/etc/nginx/sites-available/gemini-proxy`):

```nginx
# Прокси только для Gemini API (обход блокировок с Yandex VM)
# Порт 8443 — не трогаем VPN и TinyProxy на 8080.
server {
    listen 8443;
    server_name _;

    location / {
        proxy_pass https://generativelanguage.googleapis.com;
        proxy_ssl_server_name on;
        proxy_set_header Host generativelanguage.googleapis.com;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_connect_timeout 30s;
        proxy_read_timeout 120s;
        proxy_send_timeout 120s;
    }
}
```

Включить и перезагрузить:

```bash
sudo ln -sf /etc/nginx/sites-available/gemini-proxy /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

Открыть порт 8443 в файрволе (если используется):

```bash
sudo ufw allow 8443/tcp
sudo ufw status
```

### Проверка с американского сервера

```bash
curl -v -H "x-goog-api-key: ВАШ_GEMINI_API_KEY" "http://127.0.0.1:8443/v1beta/models"
```

Должен вернуться JSON со списком моделей.

## 2. На Yandex VM: .env

В `/home/marketing/marketingbot/.env` задать **только** для Gemini (без глобального HTTP_PROXY/ALL_PROXY):

```env
# Вариант Б: только Gemini через американский сервер
PROXYAPI_KEY=ВАШ_GEMINI_API_KEY
PROXYAPI_BASE_URL=http://37.1.212.51:8443
```

- `PROXYAPI_KEY` — тот же ключ, что и для Gemini (из Google AI Studio).
- `PROXYAPI_BASE_URL` — URL прокси на американском сервере: `http://IP_американского_сервера:порт` (без пути, без слэша в конце). Если nginx на 8443 — `http://37.1.212.51:8443`.

Перезапуск бота после правок .env:

```bash
sudo systemctl restart marketingbot-bot.service
```

## 3. Проверка

- В логах на VM должно быть: `GeminiService initialized via ProxyAPI.ru (bypass regional restrictions)` (или аналог в коде).
- В Telegram отправить боту сообщение — ИИ должен отвечать (без «ИИ временно недоступен»).

## Важно

- Глобальные `HTTP_PROXY`, `HTTPS_PROXY`, `ALL_PROXY` на Yandex VM **не задавать** — иначе снова пойдут через прокси и Google Sheets/OAuth, бот может зависнуть при старте.
- На американском сервере порт для Gemini (например 8443) — отдельно от TinyProxy (8080) и от VPN; меняем только конфиг nginx для Gemini.

