import sqlite3
import logging
import os
from datetime import datetime
from typing import List, Tuple, Optional, Dict

logger = logging.getLogger(__name__)

class DatabaseHandler:
    def __init__(self, db_path: str = 'data/doodlab.db'):
        self.db_path = db_path
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
    
    def get_connection(self):
        return sqlite3.connect(self.db_path)
    
    def setup_tables(self):
        """Initialize all database tables, now including the Recreation Repository."""
        try:
            conn = self.get_connection()
            c = conn.cursor()
            
            # --- Existing Tables ---
            c.execute('''CREATE TABLE IF NOT EXISTS gifts
                        (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, item_name TEXT, link TEXT, claimed_by INTEGER)''')
            
            c.execute('''CREATE TABLE IF NOT EXISTS ai_history
                        (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, role TEXT, content TEXT, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')
            
            # --- NEW: Games Repository ---
            # Status: 'seen', 'played', 'playing', 'wishlist'
            # Added: external_rating
            c.execute('''CREATE TABLE IF NOT EXISTS games
                        (id INTEGER PRIMARY KEY AUTOINCREMENT,
                         title TEXT UNIQUE,
                         category TEXT,
                         min_players INTEGER,
                         max_players INTEGER,
                         ideal_players INTEGER,
                         status TEXT DEFAULT 'seen',
                         external_rating TEXT,
                         notes TEXT,
                         release_date TEXT,
                         release_state TEXT,
                         last_update TEXT,
                         store_link TEXT,
                         added_by INTEGER,
                         created_at DATETIME DEFAULT CURRENT_TIMESTAMP)''')

            # --- NEW: Ratings/Votes ---
            # One rating per user per game to prevent ballot stuffing
            c.execute('''CREATE TABLE IF NOT EXISTS game_ratings
                        (game_id INTEGER,
                         user_id INTEGER,
                         rating INTEGER CHECK(rating >= 1 AND rating <= 10),
                         PRIMARY KEY (game_id, user_id),
                         FOREIGN KEY(game_id) REFERENCES games(id) ON DELETE CASCADE)''')

            # --- NEW: Tagging System ---
            # Allows the AI to tag games with multiple genres/vibes
            c.execute('''CREATE TABLE IF NOT EXISTS game_tags
                        (game_id INTEGER,
                         tag TEXT,
                         PRIMARY KEY (game_id, tag),
                         FOREIGN KEY(game_id) REFERENCES games(id) ON DELETE CASCADE)''')
            
            conn.commit()
            conn.close()
            logger.info("Aperture Science Database Tables Initialized.")
        except Exception as e:
            logger.error(f"Database Initialization Failed: {e}")

    # --- Game Methods ---

    def add_game(self, title: str, added_by: int, tags: List[str] = None, **kwargs) -> int:
        """Add a new simulation to the roster. Returns the new Game ID."""
        try:
            conn = self.get_connection()
            c = conn.cursor()
            
            # Dynamic query building based on provided kwargs
            columns = ['title', 'added_by']
            values = [title, added_by]
            placeholders = ['?', '?']
            
            for key, value in kwargs.items():
                if value is not None:
                    columns.append(key)
                    values.append(value)
                    placeholders.append('?')
            
            query = f"INSERT INTO games ({', '.join(columns)}) VALUES ({', '.join(placeholders)})"
            c.execute(query, values)
            game_id = c.lastrowid
            conn.commit()
            conn.close()
            
            # Handle tags if provided
            if tags and game_id:
                self.add_tags(game_id, tags)
                
            return game_id
        except sqlite3.IntegrityError:
            logger.warning(f"Game '{title}' already exists in the repository.")
            return -1
        except Exception as e:
            logger.error(f"Failed to add game: {e}")
            return -1

    def rate_game(self, game_id: int, user_id: int, rating: int):
        """Submit a mandatory performance review for a simulation."""
        try:
            conn = self.get_connection()
            c = conn.cursor()
            c.execute("INSERT OR REPLACE INTO game_ratings (game_id, user_id, rating) VALUES (?, ?, ?)",
                      (game_id, user_id, rating))
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Rating failed: {e}")

    def add_tags(self, game_id: int, tags: List[str]):
        """Attach classifiction tags to a game."""
        if not tags:
            return
            
        try:
            conn = self.get_connection()
            c = conn.cursor()
            for tag in tags:
                c.execute("INSERT OR IGNORE INTO game_tags (game_id, tag) VALUES (?, ?)", (game_id, tag.lower().strip()))
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Tagging failed: {e}")

    def get_game_library(self, status_filter: Optional[str] = None) -> List[Dict]:
        """
        Retrieve the dossier of games.
        Returns a list of dictionaries containing game data + average rating.
        """
        try:
            conn = self.get_connection()
            conn.row_factory = sqlite3.Row # Allows accessing columns by name
            c = conn.cursor()
            
            query = """
                SELECT g.*, 
                       AVG(r.rating) as avg_rating,
                       GROUP_CONCAT(t.tag, ', ') as tags
                FROM games g
                LEFT JOIN game_ratings r ON g.id = r.game_id
                LEFT JOIN game_tags t ON g.id = t.game_id
            """
            
            params = []
            if status_filter:
                query += " WHERE g.status = ?"
                params.append(status_filter)
                
            query += " GROUP BY g.id ORDER BY g.title ASC"
            
            c.execute(query, params)
            rows = c.fetchall()
            conn.close()
            
            # Convert sqlite3.Row objects to real dicts
            return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Failed to fetch library: {e}")
            return []

    def update_game_status(self, title: str, status: str) -> bool:
        """Update the status of a game"""
        try:
            conn = self.get_connection()
            c = conn.cursor()
            # Ensure status matches lowercase convention if needed, or stick to passed value
            # User defaults are lowercase ('seen'), so assuming lowercase storage
            c.execute("UPDATE games SET status = ? WHERE title = ?", (status.lower(), title))
            success = c.rowcount > 0
            conn.commit()
            conn.close()
            return success
        except Exception as e:
            logger.error(f"Failed to update game status: {e}")
            return False

    def search_game_titles(self, query: str) -> List[str]:
        """Search game titles for autocomplete"""
        try:
            conn = self.get_connection()
            c = conn.cursor()
            c.execute("SELECT title FROM games WHERE title LIKE ? LIMIT 25", (f'%{query}%',))
            rows = c.fetchall()
            conn.close()
            return [r[0] for r in rows]
        except Exception as e:
            logger.error(f"Failed to search games: {e}")
            return []

    # --- AI History Methods (Kept from your original) ---
    def add_ai_message(self, user_id: int, role: str, content: str):
        try:
            conn = self.get_connection()
            c = conn.cursor()
            c.execute("INSERT INTO ai_history (user_id, role, content) VALUES (?, ?, ?)", (user_id, role, content))
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Failed to add AI message: {e}")

    def get_ai_history(self, user_id: int, limit: int = 20) -> List[Tuple[str, str]]:
        try:
            conn = self.get_connection()
            c = conn.cursor()
            c.execute("SELECT role, content FROM ai_history WHERE user_id = ? ORDER BY id DESC LIMIT ?", (user_id, limit))
            rows = c.fetchall()
            conn.close()
            return list(reversed(rows))
        except Exception as e:
            logger.error(f"Failed to get AI history: {e}")
            return []

    def clear_ai_history(self, user_id: int):
        try:
            conn = self.get_connection()
            c = conn.cursor()
            c.execute("DELETE FROM ai_history WHERE user_id = ?", (user_id,))
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Failed to clear AI history: {e}")

    def get_tags(self) -> List[str]:
        try:
            conn = self.get_connection()
            c = conn.cursor()
            c.execute("SELECT DISTINCT tag FROM game_tags")
            rows = c.fetchall()
            conn.close()
            return [r[0] for r in rows]
        except Exception as e:
            logger.error(f"Failed to get tags: {e}")
            return []

    def recommend_games(self, min_players: int = 0, tag: str = None, limit: int = 5) -> str:
        """
        Searches the DB and returns a formatted string for the AI to read.
        """
        try:
            conn = self.get_connection()
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            
            query = "SELECT title, min_players, max_players, notes FROM games WHERE 1=1"
            params = []
            
            if min_players > 0:
                query += " AND max_players >= ?"
                params.append(min_players)
            
            if tag:
                # Sub-query to find games with specific tags
                query += " AND id IN (SELECT game_id FROM game_tags WHERE tag LIKE ?)"
                params.append(f"%{tag}%")
            
            query += " ORDER BY RANDOM() LIMIT ?"
            params.append(limit)
            
            c.execute(query, params)
            rows = c.fetchall()
            conn.close()
            
            if not rows:
                return "DATABASE QUERY RESULT: No simulations found matching those criteria."
            
            # Format this into a string the AI can read
            result_text = "DATABASE QUERY RESULT (Cave Johnson's Approved List):\n"
            for row in rows:
                result_text += f"- {row['title']} (Players: {row['min_players']}-{row['max_players']}). Note: {row['notes']}\n"
            
            return result_text
            
        except Exception as e:
            logger.error(f"Recommendation failed: {e}")
            return "DATABASE ERROR: The file cabinets are jammed."
