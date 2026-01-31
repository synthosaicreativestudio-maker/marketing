import asyncio
import logging
from dotenv import load_dotenv
from sheets_gateway import AsyncGoogleSheetsGateway
from promotions_api import check_new_promotions

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def manual_check():
    load_dotenv()
    print("🚀 Запуск ручной проверки акций...")
    
    gateway = AsyncGoogleSheetsGateway()
    try:
        promotions = await check_new_promotions(gateway)
        if promotions:
            print(f"✅ НАЙДЕНО {len(promotions)} НОВЫХ АКЦИЙ:")
            for p in promotions:
                print(f"   - {p['title']} (Row: {p.get('row_index')})")
        else:
            print("⚠️ Новых акций не найдено. Проверьте:")
            print("   1. Статус = 'Активна'")
            print("   2. Дата релиза <= Сегодня")
            print("   3. Колонка NOTIFICATION_STATUS пустая (не 'SENT')")
            
    except Exception as e:
        print(f"❌ ОШИБКА: {e}")

if __name__ == "__main__":
    asyncio.run(manual_check())
