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
                        (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                         user_id INTEGER, 
                         guild_id INTEGER,
                         role TEXT, 
                         content TEXT, 
                         timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')
            
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
                         status TEXT DEFAULT 'unknown',
                         external_rating TEXT,
                         notes TEXT,
                         release_date TEXT,
                         release_state TEXT,
                         last_update TEXT,
                         store_link TEXT,
                         added_by INTEGER,
                         created_at DATETIME DEFAULT CURRENT_TIMESTAMP)''')

            # --- NEW: Ratings/Votes ---
            # One rating per user per game per server
            c.execute('''CREATE TABLE IF NOT EXISTS game_ratings
                        (game_id INTEGER,
                         user_id INTEGER,
                         guild_id INTEGER,
                         rating INTEGER CHECK(rating >= 1 AND rating <= 10),
                         PRIMARY KEY (game_id, user_id, guild_id),
                         FOREIGN KEY(game_id) REFERENCES games(id) ON DELETE CASCADE)''')

            # --- NEW: Tagging System (Normalized) ---
            # 1. Tags Table: Stores unique tag names
            c.execute('''CREATE TABLE IF NOT EXISTS tags
                        (id INTEGER PRIMARY KEY AUTOINCREMENT,
                         name TEXT UNIQUE,
                         created_at DATETIME DEFAULT CURRENT_TIMESTAMP)''')

            # 2. Game_Tags Table: Links Games to Tags via IDs
            c.execute('''CREATE TABLE IF NOT EXISTS game_tags
                        (game_id INTEGER,
                         tag_id INTEGER,
                         PRIMARY KEY (game_id, tag_id),
                         FOREIGN KEY(game_id) REFERENCES games(id) ON DELETE CASCADE,
                         FOREIGN KEY(tag_id) REFERENCES tags(id) ON DELETE CASCADE)''')
            
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

    def rate_game(self, game_id: int, user_id: int, guild_id: int, rating: int):
        """Submit a mandatory performance review for a simulation."""
        try:
            conn = self.get_connection()
            c = conn.cursor()
            c.execute("INSERT OR REPLACE INTO game_ratings (game_id, user_id, guild_id, rating) VALUES (?, ?, ?, ?)",
                      (game_id, user_id, guild_id, rating))
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Rating failed: {e}")

    def add_tags(self, game_id: int, tags: List[str]):
        """Attach classifiction tags to a game using the new normalized schema."""
        if not tags:
            return
            
        try:
            conn = self.get_connection()
            c = conn.cursor()
            
            for tag in tags:
                tag_clean = tag.strip() # maintain case for display, but search might be case-insensitive? 
                # Let's keep it simple: Store as provided, UNIQUE constraint might fail if casing differs?
                # Best practice: Store normalized or handle "INSERT OR IGNORE" carefully.
                # For now, we'll strip.
                
                # 1. Ensure tag exists in 'tags' table and get its ID
                # We use INSERT OR IGNORE then a SELECT to handle concurrency/duplicates
                c.execute("INSERT OR IGNORE INTO tags (name) VALUES (?)", (tag_clean,))
                
                # If it was ignored, we still need the ID.
                c.execute("SELECT id FROM tags WHERE name = ?", (tag_clean,))
                result = c.fetchone()
                
                if result:
                    tag_id = result[0]
                    # 2. Link game to tag
                    c.execute("INSERT OR IGNORE INTO game_tags (game_id, tag_id) VALUES (?, ?)", (game_id, tag_id))
            
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Tagging failed: {e}")

    def get_game_library(self, 
                         guild_id: int = None,
                         status_filter: Optional[str] = None, 
                         tag_filter: str = None, 
                         player_count: int = None,
                         release_state: str = None) -> List[Dict]:
        """
        Retrieve the dossier of games with optional filtering.
        Returns a list of dictionaries containing game data + average rating.
        """
        try:
            conn = self.get_connection()
            conn.row_factory = sqlite3.Row # Allows accessing columns by name
            c = conn.cursor()
            
            # Using basic concatenation for the JOIN condition parameter isn't standard SQL binding for identifiers or logic blocks unless we construct the string carefully.
            # However, we can simply bind the guild_id in the execute call.
            
            query = """
                SELECT g.*, 
                       AVG(r.rating) as avg_rating,
                       GROUP_CONCAT(t.name, ', ') as tags
                FROM games g
                LEFT JOIN game_ratings r ON g.id = r.game_id AND r.guild_id = ?
                LEFT JOIN game_tags gt ON g.id = gt.game_id
                LEFT JOIN tags t ON gt.tag_id = t.id
                WHERE 1=1
            """
            
            params = [guild_id] # Start with guild_id for the JOIN
            
            # Dynamic Filters
            if status_filter:
                query += " AND LOWER(g.status) = ?"
                params.append(status_filter.lower())
                
            if release_state:
                query += " AND LOWER(g.release_state) = ?"
                params.append(release_state.lower())
                
            if player_count is not None:
                # Find games that support this number of players
                query += " AND g.min_players <= ? AND g.max_players >= ?"
                params.append(player_count)
                params.append(player_count)
            
            if tag_filter:
                # Subquery to find games linked to a tag with similar name
                query += """ AND g.id IN (
                    SELECT gt.game_id 
                    FROM game_tags gt 
                    JOIN tags t ON gt.tag_id = t.id 
                    WHERE t.name LIKE ?
                )"""
                params.append(f"%{tag_filter}%")
            
            query += " GROUP BY g.id ORDER BY g.title ASC"
            
            c.execute(query, params)
            rows = c.fetchall()
            conn.close()
            
            # Convert sqlite3.Row objects to real dicts
            return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Failed to fetch library: {e}")
            return []

    def update_game(self, title: str, **kwargs) -> bool:
        """
        Generic update method for game fields.
        Usage: db.update_game("Factorio", status="playing", min_players=10)
        """
        try:
            if not kwargs:
                return False
                
            conn = self.get_connection()
            c = conn.cursor()
            
            # Build the SET clause dynamically
            set_clauses = []
            values = []
            
            for key, value in kwargs.items():
                if key == 'status':
                    value = value.lower()
                    
                set_clauses.append(f"{key} = ?")
                values.append(value)
            
            # Add the WHERE clause parameter
            values.append(title)
            
            query = f"UPDATE games SET {', '.join(set_clauses)} WHERE title = ?"
            
            c.execute(query, values)
            success = c.rowcount > 0
            conn.commit()
            conn.close()
            
            return success
        except Exception as e:
            logger.error(f"Failed to update game {title}: {e}")
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
    def add_ai_message(self, user_id: int, guild_id: int, role: str, content: str):
        try:
            conn = self.get_connection()
            c = conn.cursor()
            c.execute("INSERT INTO ai_history (user_id, guild_id, role, content) VALUES (?, ?, ?, ?)", (user_id, guild_id, role, content))
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Failed to add AI message: {e}")

    def get_ai_history(self, user_id: int, guild_id: int = None, limit: int = 20) -> List[Tuple[str, str]]:
        try:
            conn = self.get_connection()
            c = conn.cursor()
            
            if guild_id is None:
                # Global Context (All Servers)
                c.execute("SELECT role, content FROM ai_history WHERE user_id = ? ORDER BY id DESC LIMIT ?", (user_id, limit))
            else:
                # Local Context (Specific Server)
                c.execute("SELECT role, content FROM ai_history WHERE user_id = ? AND guild_id = ? ORDER BY id DESC LIMIT ?", (user_id, guild_id, limit))
                
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
            c.execute("SELECT name FROM tags ORDER BY name ASC")
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
                query += """ AND id IN (
                    SELECT gt.game_id 
                    FROM game_tags gt 
                    JOIN tags t ON gt.tag_id = t.id 
                    WHERE t.name LIKE ?
                )"""
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
