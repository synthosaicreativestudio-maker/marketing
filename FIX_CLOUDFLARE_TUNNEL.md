# Исправление проблемы с Cloudflare Tunnel

## Проблема
DNS для `marketingbot.trycloudflare.com` не разрешается (NXDOMAIN), поэтому мини-приложение не может загрузить акции.

## Причина
Cloudflare Tunnel настроен, но маршрут может быть не активирован полностью в Cloudflare Dashboard, или DNS еще не распространился.

## Решение

### Вариант 1: Проверить и активировать маршрут в Cloudflare Dashboard

1. Откройте https://dash.cloudflare.com
2. Перейдите в **Zero Trust** → **Networks** → **Connectors**
3. Найдите туннель `account-368-маркетинг бот` (или похожий)
4. Откройте его
5. Перейдите на вкладку **"Published application routes"**
6. Проверьте, что маршрут для `marketingbot.trycloudflare.com` активен
7. Если маршрута нет или он неактивен:
   - Создайте новый Public Hostname:
     - Subdomain: `marketingbot`
     - Domain: `trycloudflare.com`
     - Service: `http://localhost:8080`
   - Сохраните изменения

### Вариант 2: Использовать другой URL туннеля

Если в Dashboard указан другой URL (например, `marketingbot-xxxxx.trycloudflare.com`), обновите `menu.html`:

```javascript
API_BASE_URL = 'https://marketingbot-XXXXX.trycloudflare.com'; // Замените XXXXX на реальный ID
```

### Вариант 3: Пересоздать туннель

Если туннель не работает, можно пересоздать его:

1. В Cloudflare Dashboard удалите старый туннель
2. Создайте новый туннель через Dashboard
3. Скопируйте новый Tunnel Token
4. На сервере выполните:
   ```bash
   sudo systemctl stop cloudflared
   sudo cloudflared tunnel run --token <НОВЫЙ_ТОКЕН>
   ```
5. Или используйте скрипт `install_cloudflare_tunnel.sh` с новым токеном

### Вариант 4: Временное решение - использовать прокси

Если туннель не работает, можно временно использовать прокси через GitHub Pages или другой сервис, но это требует дополнительной настройки.

## Проверка работы

После исправления проверьте:

```bash
# На сервере
curl https://marketingbot.trycloudflare.com/api/promotions

# Или с другого компьютера
curl https://marketingbot.trycloudflare.com/api/promotions
```

Если запрос возвращает данные об акциях, туннель работает.

## Текущий статус

- ✅ Cloudflare Tunnel запущен на сервере
- ✅ Конфигурация указывает на `marketingbot.trycloudflare.com`
- ❌ DNS не разрешается (NXDOMAIN)
- ❌ Мини-приложение не может загрузить акции

## Следующие шаги

1. Проверьте Cloudflare Dashboard и активируйте маршрут
2. Или получите правильный URL туннеля из Dashboard
3. Обновите `menu.html` с правильным URL
4. Проверьте работу мини-приложения
