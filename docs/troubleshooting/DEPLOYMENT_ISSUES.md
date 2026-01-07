# Проблемы при развертывании

> **Примечание:** Cloudflare Tunnel больше не используется в проекте. Все акции загружаются через Google Apps Script.

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
