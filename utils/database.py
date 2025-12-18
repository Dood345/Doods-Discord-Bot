import sqlite3
import logging
from datetime import datetime
from typing import List, Tuple, Optional

logger = logging.getLogger(__name__)

class DatabaseHandler:
    def __init__(self, db_path: str = 'doodlab.db'):
        self.db_path = db_path
    
    def get_connection(self):
        """Get a database connection"""
        return sqlite3.connect(self.db_path)
    
    def setup_tables(self):
        """Initialize all database tables"""
        try:
            conn = self.get_connection()
            c = conn.cursor()
            
            # Gifts Table (Legacy support + new structure)
            c.execute('''CREATE TABLE IF NOT EXISTS gifts
                        (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                        user_id INTEGER, 
                        item_name TEXT, 
                        link TEXT, 
                        claimed_by INTEGER)''')
            
            # AI History Table (New!)
            c.execute('''CREATE TABLE IF NOT EXISTS ai_history
                        (id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER,
                        role TEXT,
                        content TEXT,
                        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')
            
            conn.commit()
            conn.close()
            logger.info("Database tables initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize database tables: {e}")

    # --- AI History Methods ---
    
    def add_ai_message(self, user_id: int, role: str, content: str):
        """Add a message to AI history"""
        try:
            conn = self.get_connection()
            c = conn.cursor()
            c.execute("INSERT INTO ai_history (user_id, role, content) VALUES (?, ?, ?)",
                      (user_id, role, content))
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Failed to add AI message: {e}")

    def get_ai_history(self, user_id: int, limit: int = 20) -> List[Tuple[str, str]]:
        """
        Get recent chat history for context. 
        Returns list of (role, content) tuples in chronological order.
        """
        try:
            conn = self.get_connection()
            c = conn.cursor()
            # Get last N messages
            c.execute("""
                SELECT role, content 
                FROM ai_history 
                WHERE user_id = ? 
                ORDER BY id DESC 
                LIMIT ?
            """, (user_id, limit))
            
            rows = c.fetchall()
            conn.close()
            
            # Reverse to return in chronological order (oldest -> newest)
            return list(reversed(rows))
        except Exception as e:
            logger.error(f"Failed to get AI history: {e}")
            return []

    def clear_ai_history(self, user_id: int):
        """Clear history for a user (Soft delete or hard delete? Let's do hard delete for now)"""
        try:
            conn = self.get_connection()
            c = conn.cursor()
            c.execute("DELETE FROM ai_history WHERE user_id = ?", (user_id,))
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Failed to clear AI history: {e}")
