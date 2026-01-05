"""
Скрипт для инициализации базы данных.
Создает все таблицы для работы с обращениями.
"""
from db.database import init_db, engine
from db.models import Base, Appeal, AppealMessage, SpecialistResponse

if __name__ == "__main__":
    print("Инициализация базы данных...")
    print(f"Используется БД: {engine.url}")
    
    # Создаем все таблицы
    Base.metadata.create_all(bind=engine)
    
    print("✅ База данных успешно инициализирована!")
    print("Созданы таблицы:")
    print("  - appeals (обращения)")
    print("  - appeal_messages (сообщения)")
    print("  - specialist_responses (ответы специалистов)")
