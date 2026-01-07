# Проверка URL Cloudflare Tunnel

## Текущая ситуация

- Туннель настроен с hostname: `marketingbot.trycloudflare.com`
- DNS пока не разрешается (может занять до 15-30 минут)
- Все сервисы работают корректно

## Как проверить точный URL в Cloudflare Dashboard

1. Откройте Cloudflare Dashboard: https://dash.cloudflare.com
2. Перейдите в **Zero Trust** → **Networks** → **Connectors**
3. Найдите туннель `account-368-маркетинг бот`
4. Откройте его
5. Перейдите на вкладку **"Published application routes"**
6. Там будет указан точный URL (может отличаться от `marketingbot.trycloudflare.com`)

## Возможные варианты URL

- `https://marketingbot.trycloudflare.com` (тот, что мы настроили)
- `https://marketingbot-xxxxx.trycloudflare.com` (с случайным ID)
- Другой формат, указанный в Dashboard

## Что делать дальше

1. **Проверьте точный URL в Cloudflare Dashboard** (см. выше)
2. **Если URL отличается**, обновите `menu.html`:
   - Откройте `menu.html`
   - Найдите строку: `API_BASE_URL = 'https://marketingbot.trycloudflare.com';`
   - Замените на реальный URL из Dashboard
   - Закоммитьте и запушьте изменения

3. **Подождите распространения DNS** (15-30 минут)
   - После этого проверьте: `curl https://ваш-url.trycloudflare.com/api/promotions`

4. **Проверьте мини-приложение в Telegram**
   - Откройте бот → Личный кабинет → Акции
   - Проверьте консоль браузера (F12) на наличие ошибок

## Проверка работы туннеля

На сервере выполните:
```bash
# Проверить статус туннеля
sudo systemctl status cloudflared

# Проверить логи
sudo journalctl -u cloudflared -f

# Проверить локальный API
curl http://localhost:8080/api/promotions
```

## Если DNS не разрешается через 30 минут

1. Проверьте, что маршрут создан правильно в Cloudflare Dashboard
2. Убедитесь, что туннель активен (статус HEALTHY)
3. Попробуйте пересоздать маршрут в Dashboard
4. Проверьте, что используется правильный домен `trycloudflare.com`
