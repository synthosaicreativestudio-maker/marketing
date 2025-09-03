# Система точек отката проекта Marketing Telegram Bot

## Обзор

Система точек отката позволяет сохранять стабильные состояния проекта и быстро восстанавливаться к ним при необходимости.

## Структура точек отката

```
rollback_points/
├── latest_rollback.txt                    # ID последней точки отката
├── rollback_20250902_HHMMSS/             # Директория точки отката
│   ├── ROLLBACK_INFO.md                  # Метаданные и описание
│   ├── restore.sh                        # Скрипт восстановления
│   ├── bot.py                           # Основные файлы проекта
│   ├── config_manager.py                # ...
│   └── ...                              # Все файлы проекта
└── rollback_20250902_HHMMSS.tar.gz      # Архив точки отката
```

## Создание точки отката

### Полное создание
```bash
# Создать новую точку отката с текущим состоянием
./create_rollback_point.sh
```

**Что сохраняется:**
- ✅ Все Python файлы проекта
- ✅ Конфигурационные файлы (config.ini, requirements.txt)
- ✅ Системные файлы управления (.service, .plist, .sh)
- ✅ Документация и README файлы
- ✅ Кэши состояния (auth_cache.json, mcp_context_data.json)
- ✅ Метаданные точки отката
- ✅ Скрипт восстановления
- ✅ Сжатый архив для долгосрочного хранения

**Что НЕ сохраняется (по соображениям безопасности):**
- ❌ Файл .env (сохраняется замаскированная версия)
- ❌ credentials.json (содержит секретные ключи)
- ❌ Логи (bot.log)
- ❌ Временные файлы (.lock, .pid)

## Восстановление из точки отката

### Быстрое восстановление
```bash
# Восстановить из последней точки отката
./quick_restore.sh
```

### Восстановление из конкретной точки
```bash
# Перейти в директорию нужной точки отката
cd rollback_points/rollback_20250902_HHMMSS/

# Выполнить восстановление
./restore.sh
```

### Восстановление из архива
```bash
# Распаковать архив
cd rollback_points/
tar -xzf rollback_20250902_HHMMSS.tar.gz

# Восстановить
cd rollback_20250902_HHMMSS/
./restore.sh
```

## Проверка после восстановления

После восстановления обязательно выполните проверку:

```bash
# 1. Проверить статус бота
./manage_bot.sh status

# 2. Проверить логи на ошибки
./manage_bot.sh logs

# 3. Запустить диагностические тесты
python3 test_improvements.py

# 4. Проверить конфигурацию
python3 -c "from config_manager import ConfigManager; print('Config OK')"
```

## Управление точками отката

### Просмотр доступных точек отката
```bash
# Показать все точки отката
ls -la rollback_points/rollback_*/

# Показать последнюю точку отката
cat rollback_points/latest_rollback.txt

# Показать информацию о точке отката
cat rollback_points/rollback_20250902_HHMMSS/ROLLBACK_INFO.md
```

### Очистка старых точек отката
```bash
# Удалить точки отката старше 30 дней
find rollback_points/ -name "rollback_*" -type d -mtime +30 -exec rm -rf {} \;

# Удалить старые архивы
find rollback_points/ -name "*.tar.gz" -mtime +30 -delete
```

## Рекомендации по использованию

### Когда создавать точки отката:

1. **Перед критическими изменениями:**
   - Обновление основной логики бота
   - Изменение системы управления процессами
   - Обновление зависимостей

2. **После успешного решения проблем:**
   - Исправление критических багов
   - Внедрение новых функций
   - Стабилизация системы

3. **Перед deployment в production:**
   - Финальная версия для боевого сервера
   - После полного тестирования

### Периодичность создания:
- **Ежедневно** - при активной разработке
- **Еженедельно** - при стабильной эксплуатации
- **По требованию** - перед важными изменениями

### Хранение:
- **Локальные точки отката:** Последние 7 дней
- **Архивы:** Последние 30 дней
- **Критические точки:** Долгосрочное хранение

## Автоматизация

### Автоматическое создание точек отката
```bash
# Добавить в crontab для ежедневного создания
0 2 * * * cd /Users/verakoroleva/Desktop/@marketing && ./create_rollback_point.sh > /dev/null 2>&1
```

### Автоматическая очистка
```bash
# Добавить в crontab для еженедельной очистки
0 3 * * 0 find /Users/verakoroleva/Desktop/@marketing/rollback_points/ -name "rollback_*" -type d -mtime +7 -exec rm -rf {} \;
```

## Интеграция с CI/CD

```yaml
# Пример для GitHub Actions
name: Create Rollback Point
on:
  push:
    branches: [main]
    
jobs:
  rollback:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Create rollback point
        run: ./create_rollback_point.sh
      - name: Upload rollback archive
        uses: actions/upload-artifact@v2
        with:
          name: rollback-point
          path: rollback_points/*.tar.gz
```

## Troubleshooting

### Проблема: Скрипт восстановления не выполняется
```bash
# Проверить права доступа
chmod +x rollback_points/rollback_*/restore.sh

# Проверить целостность файлов
ls -la rollback_points/rollback_*/
```

### Проблема: Неполное восстановление
```bash
# Проверить логи восстановления
./restore.sh 2>&1 | tee restore.log

# Вручную скопировать недостающие файлы
cp rollback_points/rollback_YYYYMMDD_HHMMSS/missing_file.py .
```

### Проблема: Бот не запускается после восстановления
```bash
# Проверить зависимости
pip3 install -r requirements.txt

# Проверить конфигурацию
python3 -c "import config; print('Config OK')"

# Проверить файлы секретов (нужно восстановить вручную)
ls -la .env credentials.json
```

## Безопасность

⚠️ **ВАЖНО:** Точки отката НЕ содержат секретные данные (.env, credentials.json). После восстановления необходимо:

1. Восстановить файл `.env` из безопасного источника
2. Восстановить `credentials.json` из безопасного источника
3. Проверить права доступа на эти файлы (600)

```bash
# Восстановление секретов после отката
cp /secure/backup/.env .
cp /secure/backup/credentials.json .
chmod 600 .env credentials.json
```