# 🚀 MCP Setup Guide - Marketing Bot

## 📋 Обзор

Это руководство по настройке Model Context Protocol (MCP) для максимально эффективной работы с проектом Marketing Bot. MCP обеспечивает стандартизированное взаимодействие между AI и внешними инструментами.

## 🎯 Подключенные MCP серверы

### **Всего серверов: 35**

#### **📁 Файловая система и базы данных**
- **filesystem** - Доступ к файловой системе проекта
- **sqlite** - SQLite база данных для персистентности
- **postgres** - PostgreSQL для продвинутых операций
- **mysql** - MySQL для операций с данными

#### **🌐 Веб и поиск**
- **brave-search** - Веб-поиск и исследования
- **puppeteer** - Автоматизация браузера и скрапинг
- **news** - Новости и текущие события
- **weather** - Погодная информация

#### **📱 Социальные сети**
- **twitter** - Twitter/X интеграция
- **reddit** - Reddit контент и сообщества
- **linkedin** - LinkedIn профессиональная сеть
- **youtube** - YouTube контент и анализ

#### **☁️ Облачные платформы**
- **aws** - Amazon Web Services
- **gcp** - Google Cloud Platform
- **docker** - Управление контейнерами
- **kubernetes** - Управление кластерами

#### **💬 Коммуникации**
- **telegram** - Telegram Bot API (усиленная интеграция)
- **slack** - Slack workspace интеграция
- **discord** - Discord bot интеграция
- **gmail** - Gmail управление

#### **📊 Google сервисы**
- **google-drive** - Google Drive файлы
- **google-sheets** - Google Sheets (усиленная)
- **google-calendar** - Google Calendar события

#### **🤖 AI сервисы**
- **openai** - OpenAI API (усиленная)
- **anthropic** - Anthropic Claude API
- **sequential-thinking** - Последовательное мышление
- **memory** - Персистентная память

#### **📋 Управление проектами**
- **github** - GitHub интеграция
- **jira** - Jira управление задачами
- **confluence** - Confluence документация
- **notion** - Notion workspace
- **airtable** - Airtable база данных

#### **⚡ Автоматизация**
- **zapier** - Zapier автоматизация
- **ifttt** - IFTTT интеграция
- **webhook** - Webhook управление
- **cron** - Планировщик задач

#### **🔧 DevOps и мониторинг**
- **monitoring** - Системный мониторинг
- **logging** - Централизованное логирование
- **metrics** - Метрики производительности
- **security** - Сканирование безопасности
- **backup** - Автоматические бэкапы
- **deployment** - Автоматическое развертывание

## 🛠️ Настройка

### **1. Установка зависимостей**

```bash
# Установка Node.js (если не установлен)
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.0/install.sh | bash
nvm install node
nvm use node

# Установка npm пакетов для MCP серверов
npm install -g @modelcontextprotocol/server-filesystem
npm install -g @modelcontextprotocol/server-sqlite
npm install -g @modelcontextprotocol/server-postgres
npm install -g @modelcontextprotocol/server-mysql
npm install -g @modelcontextprotocol/server-brave-search
npm install -g @modelcontextprotocol/server-puppeteer
npm install -g @modelcontextprotocol/server-git
npm install -g @modelcontextprotocol/server-github
npm install -g @modelcontextprotocol/server-docker
npm install -g @modelcontextprotocol/server-kubernetes
npm install -g @modelcontextprotocol/server-aws
npm install -g @modelcontextprotocol/server-gcp
npm install -g @modelcontextprotocol/server-slack
npm install -g @modelcontextprotocol/server-discord
npm install -g @modelcontextprotocol/server-telegram
npm install -g @modelcontextprotocol/server-openai
npm install -g @modelcontextprotocol/server-anthropic
npm install -g @modelcontextprotocol/server-sequential-thinking
npm install -g @modelcontextprotocol/server-memory
npm install -g @modelcontextprotocol/server-time
npm install -g @modelcontextprotocol/server-weather
npm install -g @modelcontextprotocol/server-news
npm install -g @modelcontextprotocol/server-youtube
npm install -g @modelcontextprotocol/server-reddit
npm install -g @modelcontextprotocol/server-twitter
npm install -g @modelcontextprotocol/server-linkedin
npm install -g @modelcontextprotocol/server-google-drive
npm install -g @modelcontextprotocol/server-google-sheets
npm install -g @modelcontextprotocol/server-google-calendar
npm install -g @modelcontextprotocol/server-gmail
npm install -g @modelcontextprotocol/server-jira
npm install -g @modelcontextprotocol/server-confluence
npm install -g @modelcontextprotocol/server-notion
npm install -g @modelcontextprotocol/server-airtable
npm install -g @modelcontextprotocol/server-zapier
npm install -g @modelcontextprotocol/server-ifttt
npm install -g @modelcontextprotocol/server-webhook
npm install -g @modelcontextprotocol/server-cron
npm install -g @modelcontextprotocol/server-monitoring
npm install -g @modelcontextprotocol/server-logging
npm install -g @modelcontextprotocol/server-metrics
npm install -g @modelcontextprotocol/server-security
npm install -g @modelcontextprotocol/server-backup
npm install -g @modelcontextprotocol/server-deployment
```

### **2. Настройка переменных окружения**

```bash
# Копируем шаблон
cp mcp_env_template.env .env

# Редактируем файл с реальными API ключами
nano .env
```

### **3. Настройка Cursor**

1. **Откройте Cursor**
2. **Перейдите в Settings** (Cmd/Ctrl + ,)
3. **Найдите раздел "Model Context Protocol"**
4. **Добавьте конфигурацию MCP:**

```json
{
  "mcpServers": {
    "filesystem": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "/Users/verakoroleva/Desktop/@marketing"]
    },
    "sqlite": {
      "command": "npx", 
      "args": ["-y", "@modelcontextprotocol/server-sqlite", "--db-path", "/Users/verakoroleva/Desktop/@marketing/bot_data.db"]
    }
    // ... остальные серверы из mcp_config.json
  }
}
```

### **4. Проверка подключения**

```bash
# Проверка статуса MCP серверов
npx @modelcontextprotocol/server-filesystem --help
npx @modelcontextprotocol/server-sqlite --help

# Тест подключения к базе данных
sqlite3 bot_data.db "SELECT 1;"
```

## 🔑 Получение API ключей

### **Критически важные (для основного функционала)**
- **TELEGRAM_TOKEN** - [@BotFather](https://t.me/botfather)
- **OPENAI_API_KEY** - [OpenAI Platform](https://platform.openai.com/api-keys)
- **GITHUB_TOKEN** - [GitHub Settings](https://github.com/settings/tokens)

### **Рекомендуемые (для расширенного функционала)**
- **BRAVE_API_KEY** - [Brave Search API](https://brave.com/search/api/)
- **GOOGLE_APPLICATION_CREDENTIALS** - [Google Cloud Console](https://console.cloud.google.com/)
- **AWS_ACCESS_KEY_ID** - [AWS IAM](https://console.aws.amazon.com/iam/)

### **Дополнительные (для специфических задач)**
- **SLACK_BOT_TOKEN** - [Slack API](https://api.slack.com/apps)
- **DISCORD_BOT_TOKEN** - [Discord Developer Portal](https://discord.com/developers/applications)
- **NEWS_API_KEY** - [News API](https://newsapi.org/)
- **OPENWEATHER_API_KEY** - [OpenWeatherMap](https://openweathermap.org/api)

## 🚀 Использование

### **Базовые команды**

```bash
# Запуск с MCP
cursor --mcp-config mcp_config.json

# Проверка статуса серверов
ps aux | grep mcp

# Логи MCP
tail -f mcp.log
```

### **Примеры использования**

#### **1. Файловые операции**
```python
# Чтение файла через MCP
file_content = mcp_filesystem.read_file("bot.py")

# Запись файла через MCP
mcp_filesystem.write_file("new_file.py", content)
```

#### **2. База данных**
```python
# SQLite операции
result = mcp_sqlite.query("SELECT * FROM users WHERE active = 1")

# PostgreSQL операции
result = mcp_postgres.query("SELECT COUNT(*) FROM tickets")
```

#### **3. Веб-поиск**
```python
# Поиск в интернете
results = mcp_brave_search.search("telegram bot best practices")

# Автоматизация браузера
mcp_puppeteer.navigate("https://example.com")
screenshot = mcp_puppeteer.screenshot()
```

#### **4. Социальные сети**
```python
# Twitter поиск
tweets = mcp_twitter.search("marketing automation")

# YouTube анализ
videos = mcp_youtube.search("telegram bot tutorial")
```

#### **5. Облачные сервисы**
```python
# AWS S3
mcp_aws.s3_upload("backup.zip", "my-bucket")

# Google Drive
mcp_google_drive.upload("document.pdf")
```

## 🔧 Troubleshooting

### **Частые проблемы**

#### **1. MCP сервер не запускается**
```bash
# Проверка Node.js
node --version
npm --version

# Переустановка пакета
npm uninstall -g @modelcontextprotocol/server-filesystem
npm install -g @modelcontextprotocol/server-filesystem
```

#### **2. Ошибки API ключей**
```bash
# Проверка переменных окружения
echo $TELEGRAM_TOKEN
echo $OPENAI_API_KEY

# Перезагрузка .env файла
source .env
```

#### **3. Проблемы с базой данных**
```bash
# Проверка SQLite
sqlite3 bot_data.db ".tables"

# Создание базы если не существует
sqlite3 bot_data.db "CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY);"
```

#### **4. Проблемы с правами доступа**
```bash
# Проверка прав на файлы
ls -la mcp_config.json
chmod 644 mcp_config.json

# Проверка прав на директории
ls -la /Users/verakoroleva/Desktop/@marketing/
```

### **Логи и отладка**

```bash
# Включение debug режима
export DEBUG=true
export LOG_LEVEL=DEBUG

# Просмотр логов
tail -f mcp.log | grep ERROR
tail -f mcp.log | grep WARN

# Очистка логов
> mcp.log
```

## 📊 Мониторинг

### **Статус серверов**
```bash
# Проверка активных MCP процессов
ps aux | grep mcp | grep -v grep

# Проверка портов
netstat -an | grep LISTEN | grep mcp

# Проверка использования ресурсов
top -p $(pgrep -f mcp)
```

### **Метрики производительности**
```bash
# Время ответа MCP серверов
curl -w "@curl-format.txt" -o /dev/null -s "http://localhost:3000/mcp/health"

# Использование памяти
ps -o pid,ppid,cmd,%mem,%cpu -p $(pgrep -f mcp)
```

## 🔒 Безопасность

### **Рекомендации**
1. **Никогда не коммитьте .env файлы**
2. **Используйте минимальные права доступа для API ключей**
3. **Регулярно ротируйте API ключи**
4. **Мониторьте использование API**
5. **Используйте HTTPS для всех соединений**

### **Проверка безопасности**
```bash
# Сканирование на уязвимости
npm audit

# Проверка конфигурации
npx @modelcontextprotocol/server-security --scan mcp_config.json
```

## 📈 Оптимизация

### **Производительность**
- **Кэширование** результатов частых запросов
- **Асинхронные вызовы** для долгих операций
- **Пул соединений** для баз данных
- **Batch операции** для множественных запросов

### **Масштабирование**
- **Горизонтальное масштабирование** MCP серверов
- **Load balancing** для высоконагруженных серверов
- **Мониторинг ресурсов** и автоматическое масштабирование

## 📚 Дополнительные ресурсы

- **Официальная документация MCP**: [Model Context Protocol](https://modelcontextprotocol.io/)
- **Cursor MCP Guide**: [Cursor MCP Documentation](https://cursor.sh/docs/mcp)
- **GitHub MCP Servers**: [MCP Servers Repository](https://github.com/modelcontextprotocol/servers)

---

**Последнее обновление**: 2025-01-03 09:15
**Версия**: 1.0
**Статус**: Актуально
**Ответственный**: AI Assistant + User
