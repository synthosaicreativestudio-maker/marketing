# 🎉 Диаграмма потока данных акций Marketing Bot

## 📊 Общая архитектура

```mermaid
graph TB
    subgraph "Google Sheets"
        GS[Таблица 'Акции']
        GS --> A[Колонка A: Дата релиза]
        GS --> B[Колонка B: Название]
        GS --> C[Колонка C: Описание]
        GS --> D[Колонка D: Статус]
        GS --> E[Колонка E: Дата начала]
        GS --> F[Колонка F: Дата окончания]
        GS --> G[Колонка G: Контент]
        GS --> H[Колонка H: Опубликовать]
        GS --> I[Колонка I: Уведомление отправлено]
    end

    subgraph "PromotionsClient"
        PC[PromotionsClient]
        PC --> GNP[get_new_published_promotions]
        PC --> GAP[get_active_promotions]
        PC --> MNS[mark_notification_sent]
        PC --> PMC[_process_media_content]
    end

    subgraph "Bot Core"
        BOT[Bot Class]
        BOT --> MON[monitor_new_promotions]
        BOT --> SEND[_send_promotion_notification]
        BOT --> MENU[menu_command]
        BOT --> WEB[web_app_data]
    end

    subgraph "Mini App"
        MA[spa_menu.html]
        MA --> LOAD[loadPromotions]
        MA --> RENDER[renderPromotions]
        MA --> SEND_DATA[sendToBot]
    end

    subgraph "Users"
        U1[Авторизованные пользователи]
        U2[Пользователи мини-приложения]
    end

    %% Connections
    GS --> PC
    PC --> BOT
    BOT --> U1
    BOT --> MA
    MA --> U2
    U2 --> MA
    MA --> BOT
```

## 🔄 Детальный поток данных

### 1. **Создание акции в Google Sheets**

```mermaid
sequenceDiagram
    participant Admin as Администратор
    participant GS as Google Sheets
    participant PC as PromotionsClient
    participant BOT as Bot
    participant Users as Пользователи

    Admin->>GS: Создает акцию
    Note over GS: Заполняет поля:<br/>- Название<br/>- Описание<br/>- Даты<br/>- Контент<br/>- Статус: "Ожидает"
    
    Admin->>GS: Меняет статус на "Опубликовано"
    Note over GS: Статус: "Опубликовано"<br/>Уведомление: пустое
```

### 2. **Мониторинг новых акций**

```mermaid
sequenceDiagram
    participant BOT as Bot
    participant PC as PromotionsClient
    participant GS as Google Sheets
    participant Users as Авторизованные пользователи

    loop Каждые 30 секунд
        BOT->>PC: monitor_new_promotions()
        PC->>GS: get_new_published_promotions()
        GS-->>PC: Список новых акций
        
        alt Есть новые акции
            PC-->>BOT: Данные акций
            BOT->>BOT: _send_promotion_notification()
            BOT->>Users: Отправляет уведомления
            BOT->>PC: mark_notification_sent(row)
            PC->>GS: Помечает "отправлено"
        end
    end
```

### 3. **Отображение акций в мини-приложении**

```mermaid
sequenceDiagram
    participant User as Пользователь
    participant MA as Mini App
    participant BOT as Bot
    participant PC as PromotionsClient
    participant GS as Google Sheets

    User->>MA: Открывает "Акции и мероприятия"
    User->>MA: Нажимает "Акции"
    MA->>MA: goToPromotions()
    MA->>MA: loadPromotions()
    
    Note over MA: Показывает загрузку
    
    MA->>MA: renderPromotions(mockPromotions)
    Note over MA: Отображает акции или<br/>"Актуальных акций пока нет"
```

### 4. **Получение активных акций**

```mermaid
sequenceDiagram
    participant BOT as Bot
    participant PC as PromotionsClient
    participant GS as Google Sheets

    BOT->>PC: get_active_promotions()
    PC->>GS: Читает все данные таблицы
    
    loop Для каждой строки
        PC->>PC: Проверяет статус == "Активна"
        alt Статус "Активна"
            PC->>PC: _process_media_content()
            PC->>PC: _determine_ui_status()
            PC->>PC: _get_sort_priority()
        end
    end
    
    PC->>PC: Сортирует по приоритету
    PC-->>BOT: Список активных акций
```

## 📋 Структура данных

### **Google Sheets структура:**

| Колонка | Поле | Описание | Пример |
|---------|------|----------|---------|
| A | Дата релиза | Дата создания акции | 01.01.2025 |
| B | Название | Название акции | "Новогодняя скидка" |
| C | Описание | Подробное описание | "Скидка 20% на все товары" |
| D | Статус | Статус акции | "Опубликовано", "Активна", "Закончена" |
| E | Дата начала | Дата начала акции | 01.01.2025 |
| F | Дата окончания | Дата окончания акции | 31.01.2025 |
| G | Контент | Медиа контент | "https://drive.google.com/..." |
| H | Опубликовать | Кнопка публикации | (кнопка) |
| I | Уведомление отправлено | Статус уведомления | "отправлено" |

### **Статусы акций:**

1. **"Ожидает"** - акция создана, но не опубликована
2. **"Опубликовано"** - акция опубликована, уведомления отправлены
3. **"Активна"** - акция активна и отображается в мини-приложении
4. **"Закончена"** - акция завершена

### **UI статусы для мини-приложения:**

1. **"active"** - акция активна (зеленый)
2. **"published"** - акция опубликована, скоро стартует (желтый)
3. **"finished"** - акция завершена (красный)

## 🔧 Обработка медиа контента

### **Поддерживаемые типы медиа:**

1. **Google Drive ссылки**
   - Конвертируются в прямые ссылки
   - Формат: `https://drive.google.com/uc?export=view&id={file_id}`

2. **YouTube ссылки**
   - Конвертируются в embed ссылки
   - Формат: `https://www.youtube.com/embed/{video_id}`

3. **Прямые ссылки на изображения**
   - `.jpg`, `.jpeg`, `.png`, `.gif`, `.webp`

4. **Прямые ссылки на видео**
   - `.mp4`, `.webm`, `.ogg`

### **Пример обработки контента:**

```python
# Входные данные
content = "https://drive.google.com/file/d/1ABC123/view, https://youtube.com/watch?v=xyz789"

# Результат обработки
media_list = [
    {'type': 'image', 'url': 'https://drive.google.com/uc?export=view&id=1ABC123'},
    {'type': 'video', 'url': 'https://www.youtube.com/embed/xyz789'}
]
```

## ⚙️ Конфигурация

### **PROMOTIONS_CONFIG:**

```python
PROMOTIONS_CONFIG = {
    'SHEET_NAME': 'Акции',
    'MONITORING_INTERVAL': 30,  # 30 секунд
    'CACHE_TTL': 600,  # 10 минут
    'NOTIFICATION_DELAY': 2,  # 2 секунды между уведомлениями
    'MAX_DESCRIPTION_LENGTH': 200,  # Максимальная длина описания
}
```

## 🚀 Жизненный цикл акции

```mermaid
stateDiagram-v2
    [*] --> Создана: Администратор создает акцию
    Создана --> Ожидает: Статус "Ожидает"
    Ожидает --> Опубликовано: Статус "Опубликовано"
    Опубликовано --> Уведомления: Отправка уведомлений
    Уведомления --> Активна: Статус "Активна"
    Активна --> Отображение: Показ в мини-приложении
    Отображение --> Закончена: Дата окончания
    Закончена --> [*]
    
    note right of Опубликовано: Мониторинг каждые 30 сек
    note right of Активна: Отображается в мини-приложении
    note right of Закончена: Скрывается из мини-приложения
```

## 🔍 Ключевые методы

### **PromotionsClient:**

1. **`get_new_published_promotions()`**
   - Ищет акции со статусом "Опубликовано" без отправленного уведомления
   - Возвращает список для отправки уведомлений

2. **`get_active_promotions()`**
   - Ищет акции со статусом "Активна"
   - Обрабатывает медиа контент
   - Определяет UI статус
   - Сортирует по приоритету

3. **`mark_notification_sent(row)`**
   - Помечает акцию как уведомление отправлено
   - Обновляет колонку "Уведомление отправлено"

4. **`_process_media_content(content)`**
   - Обрабатывает ссылки на медиа
   - Конвертирует Google Drive и YouTube ссылки
   - Определяет тип медиа (image/video)

### **Bot методы:**

1. **`monitor_new_promotions()`**
   - Фоновая задача каждые 30 секунд
   - Получает новые акции
   - Отправляет уведомления авторизованным пользователям

2. **`menu_command()`**
   - Обрабатывает команду /menu
   - Получает активные акции
   - Отправляет данные в мини-приложение

3. **`web_app_data()`**
   - Обрабатывает данные от мини-приложения
   - Валидирует JSON
   - Направляет к соответствующему обработчику

## 📱 Интеграция с мини-приложением

### **Отправка данных в мини-приложение:**

```javascript
// В spa_menu.html
function sendToBot(data) {
    const jsonData = JSON.stringify(data);
    tg.sendData(jsonData);
}
```

### **Получение данных в боте:**

```python
# В bot.py
async def web_app_data(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
    raw_data = update.message.web_app_data.data
    payload = json.loads(raw_data)
    # Обработка данных...
```

## 🎯 Особенности реализации

1. **Асинхронная обработка** - все операции с Google Sheets выполняются в отдельных потоках
2. **Кэширование** - активные акции кэшируются на 10 минут
3. **Обработка ошибок** - все методы обернуты в try-catch блоки
4. **Логирование** - подробное логирование всех операций
5. **Валидация** - проверка JSON данных от мини-приложения
6. **Медиа обработка** - автоматическая конвертация ссылок
7. **Сортировка** - приоритетная сортировка акций для отображения

---

**Создано**: 2025-01-03 09:30  
**Версия**: 1.0  
**Статус**: Полный анализ функционала акций
