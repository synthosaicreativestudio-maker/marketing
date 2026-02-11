# Быстрый старт: Cloudflare Tunnel для SSL

## Что это решает?

Проблема: мини-приложение на GitHub Pages (HTTPS) не может обращаться к API на Yandex VM из-за самоподписанного SSL сертификата.

Решение: Cloudflare Tunnel предоставляет доверенный HTTPS URL для вашего API.

## Быстрая настройка (5 шагов)

### 1. Создайте туннель в Cloudflare Dashboard

1. Зайдите на https://dash.cloudflare.com (создайте аккаунт, если нужно)
2. Zero Trust → Networks → Tunnels → Create a tunnel
3. Выберите "Cloudflared", имя: `marketingbot-tunnel`
4. Скопируйте **Tunnel ID**
5. Добавьте Public Hostname:
   - Subdomain: `marketingbot`
   - Domain: `trycloudflare.com`
   - Service: `http://localhost:8080`
6. Скачайте **credentials файл** (JSON)

### 2. Запустите скрипт установки

```bash
./setup_cloudflare_tunnel.sh
```

Введите:
- Tunnel ID (из шага 1)
- Путь к credentials файлу

### 3. Обновите menu.html

Откройте `menu.html`, найдите строку:

```javascript
API_BASE_URL = 'https://marketingbot-<TUNNEL_ID>.trycloudflare.com';
```

Замените `<TUNNEL_ID>` на ваш реальный Tunnel ID.

### 4. Закоммитьте изменения

```bash
git add menu.html
git commit -m "Настроен Cloudflare Tunnel для SSL"
git push origin main
```

### 5. Проверьте работу

Откройте мини-приложение в Telegram → раздел "Акции". Акции должны загружаться без ошибок SSL.

## Проверка работы туннеля

На сервере:

```bash
./ssh_yandex.sh
sudo systemctl status cloudflared
curl https://marketingbot-<TUNNEL_ID>.trycloudflare.com/api/promotions
```

## Подробная документация

См. [docs/CLOUDFLARE_TUNNEL_SETUP.md](docs/CLOUDFLARE_TUNNEL_SETUP.md)
