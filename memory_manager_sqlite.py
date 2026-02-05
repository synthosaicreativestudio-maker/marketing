import sqlite3
import logging

logger = logging.getLogger(__name__)

class SQLiteMemoryManager:
    """Управление памятью диалогов через локальный SQLite."""
    
    def __init__(self, db_path: str = "chat_memory.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """Инициализация базы данных и создание таблиц."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    role TEXT,
                    content TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_user_id ON messages (user_id)')
            conn.commit()
            conn.close()
            logger.info(f"SQLite Memory Manager initialized at {self.db_path}")
        except Exception as e:
            logger.error(f"Failed to initialize SQLite DB: {e}")

    async def add_message(self, user_id: int, role: str, content: str):
        """Добавление сообщения в историю."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO messages (user_id, role, content) VALUES (?, ?, ?)",
                (user_id, role, content)
            )
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Error adding message to SQLite: {e}")

    async def get_history_text(self, user_id: int, limit: int = 10) -> str:
        """Получение истории в виде текста для промпта."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(
                "SELECT role, content FROM messages WHERE user_id = ? ORDER BY timestamp DESC LIMIT ?",
                (user_id, limit)
            )
            rows = cursor.fetchall()
            conn.close()
            
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
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("DELETE FROM messages WHERE user_id = ?", (user_id,))
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Error clearing SQLite history: {e}")
