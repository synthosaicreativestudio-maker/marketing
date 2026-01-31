import asyncio
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def simulate_load(count=20):
    logger.info(f"Начинаю имитацию нагрузки: {count} сообщений")
    # В реальном сценарии здесь была бы отправка сообщений через Telegram Client API
    # Но для теста Event Loop мы можем проверить, не блокируется ли он тяжелыми задачами
    for i in range(count):
        logger.info(f"Обработка имитированного сообщения {i+1}/{count}")
        await asyncio.sleep(0.1) # Имитация асинхронной работы
    logger.info("Нагрузочный тест завершен")

if __name__ == "__main__":
    asyncio.run(simulate_load())
