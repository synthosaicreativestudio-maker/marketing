# План реализации миграции на базу данных

## 🎯 Цель

Создать пошаговый план реализации миграции с Google Sheets на базу данных с мини-приложением для консультантов.

## 📦 Структура проекта после миграции

```
marketingbot/
├── api/                    # REST API
│   ├── __init__.py
│   ├── main.py            # FastAPI приложение
│   ├── models.py           # SQLAlchemy модели
│   ├── schemas.py          # Pydantic схемы
│   ├── database.py         # Подключение к БД
│   ├── routers/
│   │   ├── appeals.py      # Endpoints для обращений
│   │   ├── promotions.py   # Endpoints для акций
│   │   └── stats.py        # Статистика
│   └── services/
│       ├── appeals_db.py   # Сервис обращений (БД)
│       └── promotions_db.py # Сервис акций (БД)
├── db/
│   ├── migrations/         # Alembic миграции
│   └── database.db         # SQLite файл (или настройка PostgreSQL)
├── migrations/             # Скрипты миграции данных
│   ├── migrate_appeals.py
│   └── migrate_promotions.py
├── miniapp/               # Мини-приложение для консультантов
│   ├── index.html
│   ├── app.js
│   ├── styles.css
│   └── components/
│       ├── AppealsList.js
│       ├── AppealDetail.js
│       └── PromotionsManager.js
├── bot.py                 # Обновленный бот (использует БД)
├── requirements.txt       # Обновленные зависимости
└── .env                   # Новые переменные окружения
```

## 🔧 Шаг 1: Настройка базы данных

### 1.1 Установка зависимостей

```bash
pip install fastapi uvicorn sqlalchemy alembic pydantic
```

### 1.2 Создание структуры БД

**Файл: `api/models.py`**

```python
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime

Base = declarative_base()

class Appeal(Base):
    __tablename__ = 'appeals'
    
    id = Column(Integer, primary_key=True)
    telegram_id = Column(Integer, nullable=False, index=True)
    partner_code = Column(String(50))
    phone = Column(String(20))
    fio = Column(String(200))
    status = Column(String(50), default='новое', index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    messages = relationship("AppealMessage", back_populates="appeal", cascade="all, delete-orphan")
    responses = relationship("SpecialistResponse", back_populates="appeal", cascade="all, delete-orphan")

class AppealMessage(Base):
    __tablename__ = 'appeal_messages'
    
    id = Column(Integer, primary_key=True)
    appeal_id = Column(Integer, ForeignKey('appeals.id', ondelete='CASCADE'), nullable=False, index=True)
    message_type = Column(String(20), nullable=False)  # user, ai, specialist
    message_text = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

class SpecialistResponse(Base):
    __tablename__ = 'specialist_responses'
    
    id = Column(Integer, primary_key=True)
    appeal_id = Column(Integer, ForeignKey('appeals.id', ondelete='CASCADE'), nullable=False, index=True)
    response_text = Column(Text, nullable=False)
    specialist_name = Column(String(100))
    sent_at = Column(DateTime, default=datetime.utcnow)
    
    appeal = relationship("Appeal", back_populates="responses")

class Promotion(Base):
    __tablename__ = 'promotions'
    
    id = Column(Integer, primary_key=True)
    title = Column(String(200), nullable=False)
    description = Column(Text)
    status = Column(String(50), default='ожидает', index=True)
    start_date = Column(DateTime)
    end_date = Column(DateTime)
    release_date = Column(DateTime)
    content = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
```

## 🔌 Шаг 2: Создание REST API

### 2.1 FastAPI приложение

**Файл: `api/main.py`**

```python
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from api.database import get_db
from api.routers import appeals, promotions

app = FastAPI(title="MarketingBot API", version="1.0.0")

# CORS для мини-приложения
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # В продакшене указать конкретные домены
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Подключение роутеров
app.include_router(appeals.router, prefix="/api/appeals", tags=["appeals"])
app.include_router(promotions.router, prefix="/api/promotions", tags=["promotions"])

@app.get("/")
async def root():
    return {"message": "MarketingBot API"}

@app.get("/health")
async def health():
    return {"status": "ok"}
```

### 2.2 Endpoints для обращений

**Файл: `api/routers/appeals.py`**

```python
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from api.database import get_db
from api.models import Appeal, AppealMessage
from api.schemas import AppealCreate, AppealResponse, MessageCreate

router = APIRouter()

@router.get("/", response_model=List[AppealResponse])
def get_appeals(
    status: Optional[str] = None,
    telegram_id: Optional[int] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """Получить список обращений с фильтрами"""
    query = db.query(Appeal)
    
    if status:
        query = query.filter(Appeal.status == status)
    if telegram_id:
        query = query.filter(Appeal.telegram_id == telegram_id)
    
    return query.offset(skip).limit(limit).all()

@router.get("/{appeal_id}", response_model=AppealResponse)
def get_appeal(appeal_id: int, db: Session = Depends(get_db)):
    """Получить детали обращения"""
    appeal = db.query(Appeal).filter(Appeal.id == appeal_id).first()
    if not appeal:
        raise HTTPException(status_code=404, detail="Appeal not found")
    return appeal

@router.post("/", response_model=AppealResponse)
def create_appeal(appeal: AppealCreate, db: Session = Depends(get_db)):
    """Создать новое обращение"""
    db_appeal = Appeal(**appeal.dict())
    db.add(db_appeal)
    db.commit()
    db.refresh(db_appeal)
    return db_appeal

@router.put("/{appeal_id}/status")
def update_status(appeal_id: int, status: str, db: Session = Depends(get_db)):
    """Изменить статус обращения"""
    appeal = db.query(Appeal).filter(Appeal.id == appeal_id).first()
    if not appeal:
        raise HTTPException(status_code=404, detail="Appeal not found")
    
    appeal.status = status
    db.commit()
    return {"message": "Status updated"}

@router.post("/{appeal_id}/messages")
def add_message(appeal_id: int, message: MessageCreate, db: Session = Depends(get_db)):
    """Добавить сообщение в обращение"""
    appeal = db.query(Appeal).filter(Appeal.id == appeal_id).first()
    if not appeal:
        raise HTTPException(status_code=404, detail="Appeal not found")
    
    db_message = AppealMessage(appeal_id=appeal_id, **message.dict())
    db.add(db_message)
    db.commit()
    return {"message": "Message added"}
```

## 🔄 Шаг 3: Обновление сервисов бота

### 3.1 Новый AppealsServiceDB

**Файл: `api/services/appeals_db.py`**

```python
from sqlalchemy.orm import Session
from api.models import Appeal, AppealMessage, SpecialistResponse
from datetime import datetime
from typing import Optional, List, Dict

class AppealsServiceDB:
    def __init__(self, db: Session):
        self.db = db
    
    def create_appeal(self, telegram_id: int, partner_code: str, 
                     phone: str, fio: str, text: str) -> Appeal:
        """Создать или обновить обращение"""
        # Ищем существующее обращение
        appeal = self.db.query(Appeal).filter(
            Appeal.telegram_id == telegram_id
        ).first()
        
        if appeal:
            # Обновляем существующее
            appeal.updated_at = datetime.utcnow()
        else:
            # Создаем новое
            appeal = Appeal(
                telegram_id=telegram_id,
                partner_code=partner_code,
                phone=phone,
                fio=fio,
                status='новое'
            )
            self.db.add(appeal)
        
        # Добавляем сообщение
        message = AppealMessage(
            appeal_id=appeal.id,
            message_type='user',
            message_text=text
        )
        self.db.add(message)
        self.db.commit()
        self.db.refresh(appeal)
        
        return appeal
    
    def get_appeal_status(self, telegram_id: int) -> str:
        """Получить статус обращения"""
        appeal = self.db.query(Appeal).filter(
            Appeal.telegram_id == telegram_id
        ).first()
        return appeal.status if appeal else 'новое'
    
    def set_status_in_work(self, telegram_id: int) -> bool:
        """Установить статус 'В работе'"""
        appeal = self.db.query(Appeal).filter(
            Appeal.telegram_id == telegram_id
        ).first()
        if appeal:
            appeal.status = 'в_работе'
            appeal.updated_at = datetime.utcnow()
            self.db.commit()
            return True
        return False
    
    def add_ai_response(self, telegram_id: int, response_text: str) -> bool:
        """Добавить ответ ИИ"""
        appeal = self.db.query(Appeal).filter(
            Appeal.telegram_id == telegram_id
        ).first()
        if appeal:
            message = AppealMessage(
                appeal_id=appeal.id,
                message_type='ai',
                message_text=response_text
            )
            appeal.status = 'ответ_ии'
            appeal.updated_at = datetime.utcnow()
            self.db.add(message)
            self.db.commit()
            return True
        return False
```

## 📱 Шаг 4: Создание мини-приложения

### 4.1 HTML структура

**Файл: `miniapp/index.html`**

```html
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Консультант - MarketingBot</title>
    <script src="https://telegram.org/js/telegram-web-app.js"></script>
    <link rel="stylesheet" href="styles.css">
</head>
<body>
    <div id="app">
        <header>
            <h1>Обращения</h1>
            <div class="filters">
                <select id="statusFilter">
                    <option value="">Все статусы</option>
                    <option value="новое">Новое</option>
                    <option value="в_работе">В работе</option>
                    <option value="решено">Решено</option>
                </select>
            </div>
        </header>
        
        <div id="appealsList" class="appeals-list">
            <!-- Список обращений -->
        </div>
        
        <div id="appealDetail" class="appeal-detail" style="display: none;">
            <!-- Детали обращения -->
        </div>
    </div>
    
    <script src="app.js"></script>
</body>
</html>
```

### 4.2 JavaScript логика

**Файл: `miniapp/app.js`**

```javascript
const API_URL = 'https://your-api-url.com/api';

// Инициализация Telegram WebApp
const tg = window.Telegram.WebApp;
tg.ready();
tg.expand();

// Загрузка обращений
async function loadAppeals(status = '') {
    const url = status 
        ? `${API_URL}/appeals?status=${status}`
        : `${API_URL}/appeals`;
    
    const response = await fetch(url);
    const appeals = await response.json();
    
    renderAppeals(appeals);
}

// Отображение списка обращений
function renderAppeals(appeals) {
    const list = document.getElementById('appealsList');
    list.innerHTML = appeals.map(appeal => `
        <div class="appeal-card" onclick="showAppealDetail(${appeal.id})">
            <div class="appeal-header">
                <span class="status status-${appeal.status}">${appeal.status}</span>
                <span class="date">${new Date(appeal.created_at).toLocaleDateString()}</span>
            </div>
            <div class="appeal-info">
                <strong>${appeal.fio || 'Без имени'}</strong>
                <span>${appeal.phone || ''}</span>
            </div>
        </div>
    `).join('');
}

// Показать детали обращения
async function showAppealDetail(appealId) {
    const response = await fetch(`${API_URL}/appeals/${appealId}`);
    const appeal = await response.json();
    
    // Загрузить сообщения
    const messagesResponse = await fetch(`${API_URL}/appeals/${appealId}/messages`);
    const messages = await messagesResponse.json();
    
    renderAppealDetail(appeal, messages);
}

// Отправить ответ специалиста
async function sendResponse(appealId, responseText) {
    await fetch(`${API_URL}/appeals/${appealId}/response`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ response_text: responseText })
    });
    
    loadAppeals();
}

// Инициализация
loadAppeals();

// Фильтр по статусу
document.getElementById('statusFilter').addEventListener('change', (e) => {
    loadAppeals(e.target.value);
});
```

## 🔄 Шаг 5: Миграция данных

### 5.1 Скрипт миграции обращений

**Файл: `migrations/migrate_appeals.py`**

```python
import gspread
from google.oauth2.service_account import Credentials
from sqlalchemy.orm import Session
from api.models import Appeal, AppealMessage
from api.database import SessionLocal
import os
import json

def migrate_appeals():
    # Подключение к Google Sheets
    sa_json = os.environ.get('GCP_SA_JSON')
    sa_info = json.loads(sa_json)
    creds = Credentials.from_service_account_info(sa_info)
    client = gspread.authorize(creds)
    
    sheet_id = os.environ.get('APPEALS_SHEET_ID')
    spreadsheet = client.open_by_key(sheet_id)
    worksheet = spreadsheet.worksheet('обращения')
    
    # Подключение к БД
    db = SessionLocal()
    
    try:
        records = worksheet.get_all_records()
        
        for record in records:
            telegram_id = int(record.get('telegram_id', 0))
            if not telegram_id:
                continue
            
            # Создаем обращение
            appeal = Appeal(
                telegram_id=telegram_id,
                partner_code=record.get('код', ''),
                phone=record.get('телефон', ''),
                fio=record.get('ФИО', ''),
                status=record.get('статус', 'новое')
            )
            db.add(appeal)
            db.flush()
            
            # Парсим сообщения из текста обращений
            appeals_text = record.get('текст_обращений', '')
            if appeals_text:
                # Парсинг сообщений (зависит от формата)
                # ...
                pass
            
        db.commit()
        print(f"Мигрировано {len(records)} обращений")
    finally:
        db.close()

if __name__ == '__main__':
    migrate_appeals()
```

## 🚀 Шаг 6: Обновление bot.py

### 6.1 Интеграция с новой БД

```python
# bot.py (частично)
from api.database import SessionLocal
from api.services.appeals_db import AppealsServiceDB

# В функции main()
db = SessionLocal()
appeals_service = AppealsServiceDB(db)

# Использование в handlers
def chat_handler(auth_service, openai_service, appeals_service):
    async def handle_chat(update, context):
        # Используем appeals_service как обычно
        # Но теперь он работает с БД
        pass
```

## 📝 Переменные окружения

```bash
# .env
DATABASE_URL=sqlite:///./db/database.db
# или для PostgreSQL:
# DATABASE_URL=postgresql://user:password@localhost/marketingbot

API_URL=https://your-api-url.com
API_KEY=your-secret-api-key

# Старые переменные (можно оставить для миграции)
APPEALS_SHEET_ID=...
PROMOTIONS_SHEET_ID=...
```

## ✅ Чеклист миграции

- [ ] Установить зависимости (FastAPI, SQLAlchemy, Alembic)
- [ ] Создать структуру БД (models.py)
- [ ] Настроить миграции (Alembic)
- [ ] Создать REST API (FastAPI)
- [ ] Реализовать endpoints для обращений
- [ ] Реализовать endpoints для акций
- [ ] Создать AppealsServiceDB
- [ ] Создать PromotionsServiceDB
- [ ] Обновить bot.py
- [ ] Обновить handlers.py
- [ ] Обновить response_monitor.py
- [ ] Создать мини-приложение (HTML/JS)
- [ ] Написать скрипт миграции данных
- [ ] Протестировать на staging
- [ ] Мигрировать данные
- [ ] Деплой на продакшен
- [ ] Мониторинг и исправление багов

---

**Следующий шаг**: Начать с создания структуры БД и моделей SQLAlchemy.
