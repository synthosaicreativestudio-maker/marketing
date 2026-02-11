# Настройка Cloudflare Tunnel для решения проблемы SSL

Это руководство поможет настроить Cloudflare Tunnel для получения доверенного HTTPS URL для вашего сервера Yandex VM.

## Преимущества

- ✅ Доверенный SSL сертификат (без предупреждений браузера)
- ✅ Бесплатно для личного использования
- ✅ Быстрая настройка (30-60 минут)
- ✅ Высокая надежность (Cloudflare инфраструктура)

## Предварительные требования

1. Аккаунт Cloudflare (бесплатный): https://dash.cloudflare.com/sign-up
2. Доступ к серверу Yandex VM через SSH
3. Flask приложение должно работать на `localhost:8080`

## Шаг 1: Регистрация в Cloudflare

1. Перейдите на https://dash.cloudflare.com/sign-up
2. Создайте бесплатный аккаунт
3. Войдите в Dashboard

## Шаг 2: Создание Tunnel через Dashboard

1. В Cloudflare Dashboard перейдите в **Zero Trust** (или **Networks**)
2. Выберите **Networks** → **Tunnels**
3. Нажмите **Create a tunnel**
4. Выберите тип туннеля: **Cloudflared**
5. Введите имя туннеля: `marketingbot-tunnel`
6. Нажмите **Save tunnel**
7. **Скопируйте Tunnel ID** (он понадобится позже)
8. Нажмите **Next** для настройки Public Hostname

## Шаг 3: Настройка Public Hostname

1. В разделе **Public Hostname** нажмите **Add a public hostname**
2. **Subdomain**: `marketingbot` (или любое другое имя)
3. **Domain**: выберите `trycloudflare.com` (бесплатный домен)
4. **Service Type**: `HTTP`
5. **URL**: `localhost:8080`
6. Нажмите **Save hostname**

**Важно:** Запишите полный URL туннеля (например: `https://marketingbot-xxxxx.trycloudflare.com`)

## Шаг 4: Скачивание credentials файла

1. В настройках туннеля найдите раздел **Install connector**
2. Выберите **Linux** → **amd64**
3. Скачайте **credentials файл** (JSON) - он будет называться `<TUNNEL_ID>.json`
4. Сохраните его на вашем локальном компьютере

## Шаг 5: Установка cloudflared на сервере

Подключитесь к серверу через SSH:

```bash
./ssh_yandex.sh
```

Выполните на сервере:

```bash
# Скачать cloudflared
cd /tmp
wget https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb
sudo dpkg -i cloudflared-linux-amd64.deb

# Если возникли ошибки зависимостей:
sudo apt-get install -f -y
```

## Шаг 6: Настройка туннеля на сервере

### Вариант A: Использование автоматического скрипта (рекомендуется)

1. Убедитесь, что у вас есть:
   - Tunnel ID (из шага 2)
   - Credentials файл (JSON) на локальном компьютере

2. Запустите скрипт установки:

```bash
./setup_cloudflare_tunnel.sh
```

Скрипт попросит ввести:
- Tunnel ID
- Путь к credentials файлу

### Вариант B: Ручная настройка

Если предпочитаете настроить вручную:

```bash
# Подключитесь к серверу
./ssh_yandex.sh

# Создайте директорию для конфигурации
sudo mkdir -p /etc/cloudflared

# Скопируйте credentials файл на сервер
# (выполните на локальном компьютере)
scp -i ~/.ssh/ssh-key-1767684261599/ssh-key-1767684261599 <TUNNEL_ID>.json ubuntu@158.160.0.127:/tmp/

# На сервере переместите файл
sudo mv /tmp/<TUNNEL_ID>.json /etc/cloudflared/
sudo chmod 600 /etc/cloudflared/<TUNNEL_ID>.json

# Создайте конфигурационный файл
sudo nano /etc/cloudflared/config.yml
```

Вставьте следующее содержимое (замените `<TUNNEL_ID>` на ваш реальный ID):

```yaml
tunnel: <TUNNEL_ID>
credentials-file: /etc/cloudflared/<TUNNEL_ID>.json

ingress:
  - hostname: marketingbot-<TUNNEL_ID>.trycloudflare.com
    service: http://localhost:8080
  - service: http_status:404
```

Сохраните файл (Ctrl+O, Enter, Ctrl+X).

## Шаг 7: Настройка systemd сервиса

Создайте systemd сервис для автозапуска туннеля:

```bash
sudo nano /etc/systemd/system/cloudflared.service
```

Вставьте:

```ini
[Unit]
Description=Cloudflare Tunnel
After=network.target

[Service]
Type=simple
User=root
ExecStart=/usr/local/bin/cloudflared tunnel --config /etc/cloudflared/config.yml run
Restart=on-failure
RestartSec=5s

[Install]
WantedBy=multi-user.target
```

Сохраните и запустите:

```bash
sudo systemctl daemon-reload
sudo systemctl enable cloudflared
sudo systemctl start cloudflared
```

## Шаг 8: Проверка работы туннеля

```bash
# Проверить статус сервиса
sudo systemctl status cloudflared

# Проверить логи
sudo journalctl -u cloudflared -f

# Проверить доступность API через туннель
curl https://marketingbot-<TUNNEL_ID>.trycloudflare.com/api/promotions
```

Если всё работает, вы должны увидеть JSON с акциями.

## Шаг 9: Обновление menu.html

После успешной настройки туннеля обновите `menu.html`:

1. Откройте `menu.html`
2. Найдите строку с `API_BASE_URL`
3. Замените `<TUNNEL_ID>` на ваш реальный Tunnel ID:

```javascript
API_BASE_URL = 'https://marketingbot-<ВАШ_TUNNEL_ID>.trycloudflare.com';
```

4. Сохраните и закоммитьте изменения:

```bash
git add menu.html
git commit -m "Обновлен API_BASE_URL для Cloudflare Tunnel"
git push origin main
```

## Шаг 10: Проверка мини-приложения

1. Откройте мини-приложение в Telegram
2. Перейдите в раздел "Акции"
3. Убедитесь, что акции загружаются без ошибок SSL
4. Проверьте консоль браузера (F12) - не должно быть ошибок CORS или SSL

## Устранение проблем

### Туннель не запускается

```bash
# Проверить логи
sudo journalctl -u cloudflared -n 50

# Проверить конфигурацию
sudo cloudflared tunnel --config /etc/cloudflared/config.yml validate

# Проверить credentials файл
sudo cat /etc/cloudflared/<TUNNEL_ID>.json
```

### API недоступен через туннель

1. Убедитесь, что Flask приложение работает на `localhost:8080`:
   ```bash
   curl http://localhost:8080/api/promotions
   ```

2. Проверьте, что туннель настроен правильно:
   ```bash
   sudo cat /etc/cloudflared/config.yml
   ```

3. Перезапустите туннель:
   ```bash
   sudo systemctl restart cloudflared
   ```

### Ошибки SSL в браузере

- Убедитесь, что используете правильный URL туннеля
- Проверьте, что туннель работает: `sudo systemctl status cloudflared`
- Очистите кэш браузера

## Постоянное решение (опционально)

Для постоянного URL (вместо `trycloudflare.com`):

1. Купите домен (например, через Cloudflare или другой регистратор)
2. Добавьте домен в Cloudflare
3. В настройках туннеля измените Public Hostname на ваш домен
4. Обновите `API_BASE_URL` в `menu.html`

## Полезные команды

```bash
# Остановить туннель
sudo systemctl stop cloudflared

# Запустить туннель
sudo systemctl start cloudflared

# Перезапустить туннель
sudo systemctl restart cloudflared

# Просмотр логов в реальном времени
sudo journalctl -u cloudflared -f

# Проверка статуса
sudo systemctl status cloudflared
```

## Дополнительная информация

- [Документация Cloudflare Tunnel](https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/)
- [Cloudflare Zero Trust Dashboard](https://one.dash.cloudflare.com/)
