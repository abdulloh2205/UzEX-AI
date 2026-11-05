import logging
import sqlite3
from pathlib import Path
from typing import Dict, Optional
from src.config import settings

logger = logging.getLogger(__name__)


class UserPreferencesRepository:
    """
    Persistent repository for storing Telegram user preferences (e.g. selected language)
    using an isolated SQLite database and an in-memory cache for ultra-fast lookup.
    """

    def __init__(self, db_path: Optional[Path] = None):
        if db_path is None:
            db_dir = settings.DATABASE_PATH.parent
            db_dir.mkdir(parents=True, exist_ok=True)
            self.db_path = db_dir / "user_preferences.db"
        else:
            self.db_path = Path(db_path)
            self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self._cache: Dict[int, str] = {}
        self._init_db()

    def _init_db(self) -> None:
        """Initializes user_preferences table if not exists."""
        conn = None
        try:
            conn = sqlite3.connect(self.db_path)
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS user_preferences (
                    user_id INTEGER PRIMARY KEY,
                    language TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS conversation_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_history_user_id ON conversation_history(user_id, id);
                """
            )
            conn.commit()
        except Exception as e:
            logger.error(f"Failed to initialize user preferences database: {e}")
        finally:
            if conn:
                conn.close()

    def get_language(self, user_id: int) -> Optional[str]:
        """Returns the saved language for user_id ('ru' or 'uz'), or None if not set."""
        if user_id in self._cache:
            return self._cache[user_id]

        conn = None
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(
                "SELECT language FROM user_preferences WHERE user_id = ?",
                (user_id,)
            )
            row = cursor.fetchone()
            if row:
                lang = str(row[0])
                self._cache[user_id] = lang
                return lang
        except Exception as e:
            logger.error(f"Error reading user preference for {user_id}: {e}")
        finally:
            if conn:
                conn.close()

        return None

    def set_language(self, user_id: int, language: str) -> bool:
        """Saves or updates preferred language for user_id ('ru' or 'uz')."""
        if language not in ("ru", "uz"):
            raise ValueError(f"Unsupported language code: {language}")

        self._cache[user_id] = language

        conn = None
        try:
            conn = sqlite3.connect(self.db_path)
            conn.execute(
                """
                INSERT INTO user_preferences (user_id, language, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(user_id) DO UPDATE SET
                    language = excluded.language,
                    updated_at = CURRENT_TIMESTAMP;
                """,
                (user_id, language)
            )
            conn.commit()
            return True
        except Exception as e:
            logger.error(f"Error saving user preference for {user_id}: {e}")
            return False
        finally:
            if conn:
                conn.close()

    def clear_cache(self) -> None:
        """Clears in-memory cache (primarily for tests)."""
        self._cache.clear()

    def add_message(self, user_id: int, role: str, content: str, max_history: int = 10) -> None:
        """Stores a message (role: 'user' or 'model') in conversation history."""
        if not user_id or not content.strip():
            return

        conn = None
        try:
            conn = sqlite3.connect(self.db_path)
            conn.execute(
                """
                INSERT INTO conversation_history (user_id, role, content)
                VALUES (?, ?, ?);
                """,
                (user_id, role, content.strip())
            )
            # Prune old messages exceeding max_history
            conn.execute(
                """
                DELETE FROM conversation_history
                WHERE id IN (
                    SELECT id FROM conversation_history
                    WHERE user_id = ?
                    ORDER BY id DESC
                    LIMIT -1 OFFSET ?
                );
                """,
                (user_id, max_history)
            )
            conn.commit()
        except Exception as e:
            logger.error(f"Error saving conversation turn for {user_id}: {e}")
        finally:
            if conn:
                conn.close()

    def get_history(self, user_id: int, limit: int = 6) -> list[dict]:
        """Returns the most recent conversation history for user_id in chronological order."""
        if not user_id:
            return []

        conn = None
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT role, content FROM (
                    SELECT id, role, content FROM conversation_history
                    WHERE user_id = ?
                    ORDER BY id DESC
                    LIMIT ?
                ) ORDER BY id ASC;
                """,
                (user_id, limit)
            )
            rows = cursor.fetchall()
            return [{"role": r[0], "content": r[1]} for r in rows]
        except Exception as e:
            logger.error(f"Error fetching conversation history for {user_id}: {e}")
            return []
        finally:
            if conn:
                conn.close()

    def clear_history(self, user_id: int) -> None:
        """Clears conversation history for user_id."""
        if not user_id:
            return

        conn = None
        try:
            conn = sqlite3.connect(self.db_path)
            conn.execute("DELETE FROM conversation_history WHERE user_id = ?;", (user_id,))
            conn.commit()
        except Exception as e:
            logger.error(f"Error clearing conversation history for {user_id}: {e}")
        finally:
            if conn:
                conn.close()


# Global default instance
user_preferences_repo = UserPreferencesRepository()
