import asyncio
import os
from telegram import Bot
from dotenv import load_dotenv

async def main():
    load_dotenv()
    token = os.getenv("TELEGRAM_TOKEN")
    chat_id = "284355186"
    bot = Bot(token=token)
    try:
        msg = await bot.send_message(chat_id=chat_id, text="Диагностический тест: прямое сообщение от Bot API (Python)")
        print(f"Success! Message sent: {msg.message_id}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
