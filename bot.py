import os
import logging
from dotenv import load_dotenv
from telegram.ext import Application, CommandHandler
from telegram import Update
from google_sheets_service import GoogleSheetsService
from auth_service import AuthService
from handlers import setup_handlers

# Настройка логирования
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logging.getLogger("httpx").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

async def main():
    load_dotenv()
    telegram_token = os.getenv("TELEGRAM_TOKEN")
    
    if not telegram_token:
        logger.error("TELEGRAM_TOKEN не установлен в .env файле.")
        return

    # Инициализация сервисов (пока заглушки)
    # В реальном проекте здесь будет логика инициализации GoogleSheetsService
    # и AuthService с передачей необходимых параметров, например credentials.json
    google_sheets_service = GoogleSheetsService() # Заглушка
    auth_service = AuthService(google_sheets_service) # Заглушка

    application = Application.builder().token(telegram_token).build()

    setup_handlers(application, auth_service)

    logger.info("Бот запущен...")
    await application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())