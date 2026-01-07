# Проблемы при развертывании

## Проблема: DNS не разрешается для Cloudflare Tunnel

### Симптомы
- DNS запросы к `marketingbot.trycloudflare.com` возвращают NXDOMAIN
- Мини-приложение не может загрузить акции

### Решение

#### Вариант 1: Проверить и активировать маршрут в Cloudflare Dashboard

1. Откройте https://dash.cloudflare.com
2. Перейдите в **Zero Trust** → **Networks** → **Connectors**
3. Найдите туннель
4. Откройте вкладку **"Published application routes"**
5. Проверьте, что маршрут активен
6. Если маршрута нет:
   - Создайте новый Public Hostname:
     - Subdomain: `marketingbot`
     - Domain: `trycloudflare.com`
     - Service: `http://localhost:8080`
   - Сохраните изменения

#### Вариант 2: Пересоздать маршрут

1. Удалите старый маршрут в Cloudflare Dashboard
2. Создайте новый маршрут с теми же параметрами
3. Подождите 10-15 минут для распространения DNS

#### Вариант 3: Использовать другой subdomain

Если `marketingbot` не работает, попробуйте другой subdomain:
- `marketingbot-api`
- `marketing-api`
- `api-marketingbot`

Обновите `menu.html` с новым URL.

### Проверка

```bash
# Проверка DNS
nslookup marketingbot.trycloudflare.com 8.8.8.8

# Проверка API
curl https://marketingbot.trycloudflare.com/api/promotions
```

## Проблема: Неправильный WEB_APP_URL

### Симптомы
- Мини-приложение не загружается
- В логах ошибка "WEB_APP_URL содержит невалидный URL"

### Решение

1. Проверьте значение в `.env`:
   ```bash
   grep WEB_APP_URL .env
   ```

2. Убедитесь, что значение правильное:
   ```
   WEB_APP_URL=https://synthosaicreativestudio-maker.github.io/marketing/
   ```

3. Обновите `.env` (если нужно):
   ```bash
   sed -i 's|WEB_APP_URL=.*|WEB_APP_URL=https://synthosaicreativestudio-maker.github.io/marketing/|' .env
   ```

4. Перезапустите сервисы:
   ```bash
   sudo systemctl restart marketingbot-bot.service
   sudo systemctl restart marketingbot-web.service
   ```

## Проблема: Cloudflare Tunnel не запускается

### Проверка статуса

```bash
sudo systemctl status cloudflared
```

### Просмотр логов

```bash
sudo journalctl -u cloudflared -f
```

### Переустановка туннеля

1. Остановите туннель:
   ```bash
   sudo systemctl stop cloudflared
   ```

2. Создайте новый туннель в Cloudflare Dashboard

3. Используйте скрипт установки:
   ```bash
   ./install_cloudflare_tunnel.sh
   ```

## Проблема: Ошибки при обновлении на сервере

### Проверка подключения к GitHub

```bash
cd /home/ubuntu/marketingbot
git fetch origin
git pull origin main
```

### Проверка прав доступа

```bash
sudo systemctl status marketingbot-bot.service
sudo systemctl status marketingbot-web.service
```

### Перезапуск сервисов

```bash
sudo systemctl restart marketingbot-bot.service
sudo systemctl restart marketingbot-web.service
```

## Дополнительная помощь

- [Настройка Cloudflare Tunnel](../deployment/CLOUDFLARE_TUNNEL_SETUP.md)
- [Развертывание на Yandex Cloud](../deployment/DEPLOYMENT_YANDEX.md)
- [Общее руководство по устранению неполадок](TROUBLESHOOTING.md)
