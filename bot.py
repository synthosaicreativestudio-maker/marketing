
import logging
import os

from dotenv import load_dotenv
from telegram import Update, WebAppInfo
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler
from telegram.helpers import escape_markdown

# Загружаем переменные окружения из .env файла
load_dotenv()

# Настройка логирования
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
WEB_APP_URL = os.getenv("WEB_APP_AUTH_URL")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Отправляет приветственное сообщение при команде /start."""
    user = update.effective_user
    name = escape_markdown(user.first_name or "пользователь")
    welcome_message = f"Добрый день, {name}, для продолжения вам необходимо авторизоваться"

    await update.message.reply_text(welcome_message)


def main() -> None:
    """Запускает бота."""
    if not TELEGRAM_TOKEN:
        logger.error("TELEGRAM_TOKEN не найден в .env файле!")
        return

    # Создаем приложение
    application = Application.builder().token(TELEGRAM_TOKEN).build()

    # Добавляем обработчик команды /start
    application.add_handler(CommandHandler("start", start))

    # Запускаем бота
    logger.info("Бот запускается...")
    application.run_polling()


if __name__ == "__main__":
    main()

