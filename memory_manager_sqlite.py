import logging
import os
from typing import Optional
import aiosqlite

logger = logging.getLogger(__name__)

class SQLiteMemoryManager:
    """Управление памятью диалогов через асинхронный SQLite."""
    
    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            db_path = os.getenv("SQLITE_DB_PATH", "chat_memory.db")
        
        self.db_path = db_path
        
        # Создаем директорию базы данных, если она указана и не существует
        db_dir = os.path.dirname(os.path.abspath(self.db_path))
        if db_dir and not os.path.exists(db_dir):
            try:
                os.makedirs(db_dir, exist_ok=True)
                logger.info(f"Created directory for SQLite DB: {db_dir}")
            except Exception as e:
                logger.error(f"Failed to create directory for SQLite DB {db_dir}: {e}")

    async def _init_db(self):
        """Инициализация базы данных и создание таблиц."""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute('''
                    CREATE TABLE IF NOT EXISTS messages (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER,
                        role TEXT,
                        content TEXT,
                        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                await db.execute('CREATE INDEX IF NOT EXISTS idx_user_id ON messages (user_id)')
                await db.commit()
        except Exception as e:
            logger.error(f"Failed to initialize SQLite DB: {e}")

    async def add_message(self, user_id: int, role: str, content: str):
        """Добавление сообщения в историю."""
        try:
            await self._init_db()
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    "INSERT INTO messages (user_id, role, content) VALUES (?, ?, ?)",
                    (user_id, role, content)
                )
                await db.commit()
        except Exception as e:
            logger.error(f"Error adding message to SQLite: {e}")

    async def get_history_text(self, user_id: int, limit: int = 12) -> str:
        """Получение истории в виде текста для промпта."""
        try:
            await self._init_db()
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute(
                    "SELECT role, content FROM messages WHERE user_id = ? ORDER BY timestamp DESC LIMIT ?",
                    (user_id, limit)
                ) as cursor:
                    rows = await cursor.fetchall()
            
            if not rows:
                return ""
            
            # Разворачиваем историю (она была DESC)
            history = []
            for role, content in reversed(rows):
                prefix = "Пользователь" if role == "user" else "Ассистент"
                history.append(f"{prefix}: {content}")
            
            return "\n".join(history)
        except Exception as e:
            logger.error(f"Error getting history from SQLite: {e}")
            return ""

    async def clear_history(self, user_id: int):
        """Очистка истории пользователя."""
        try:
            await self._init_db()
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("DELETE FROM messages WHERE user_id = ?", (user_id,))
                await db.commit()
        except Exception as e:
            logger.error(f"Error clearing SQLite history: {e}")
