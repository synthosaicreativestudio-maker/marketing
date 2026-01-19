"""
FastAPI приложение для REST API.
Основной файл для работы с обращениями через админ-панель.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.routers import appeals
import os
from dotenv import load_dotenv

load_dotenv()

# Создаем FastAPI приложение
app = FastAPI(
    title="MarketingBot API",
    description="REST API для работы с обращениями и админ-панелью",
    version="1.0.0"
)

# Настройка CORS для админ-панели
# В продакшене указать конкретные домены
allowed_origins = os.getenv("ALLOWED_ORIGINS", "*").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Подключение роутеров
app.include_router(appeals.router, prefix="/api/appeals", tags=["appeals"])


@app.get("/")
async def root():
    """Корневой endpoint"""
    return {
        "message": "MarketingBot API",
        "version": "1.0.0",
        "docs": "/docs"
    }


@app.get("/health")
async def health():
    """Проверка здоровья API"""
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
