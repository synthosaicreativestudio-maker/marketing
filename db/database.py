"""
Настройка подключения к базе данных.
Использует SQLite для начала, можно легко переключиться на PostgreSQL.
"""
import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

load_dotenv()

# Получаем URL БД из переменных окружения
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./db/appeals.db")

# Создаем engine
if DATABASE_URL.startswith("sqlite"):
    # Для SQLite нужен специальный параметр для поддержки foreign keys
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False}  # Для SQLite
    )
else:
    engine = create_engine(DATABASE_URL)

# Создаем фабрику сессий
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Базовый класс для моделей
Base = declarative_base()

def get_db():
    """
    Dependency для получения сессии БД.
    Используется в FastAPI endpoints.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    """
    Инициализация БД - создание всех таблиц.
    """
    # Импортируем все модели, чтобы они зарегистрировались в Base
    from db.models import Appeal, AppealMessage, SpecialistResponse
    
    # Создаем все таблицы
    Base.metadata.create_all(bind=engine)
    print("База данных инициализирована")
