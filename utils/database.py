import aiosqlite
import logging
import os
from datetime import datetime
from typing import List, Tuple, Optional, Dict

logger = logging.getLogger(__name__)

class DatabaseHandler:
    def __init__(self, db_path: str = 'data/doodlab.db'):
        self.db_path = db_path
        if self.db_path != ":memory:":
            os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
    
    def get_connection(self):
        return aiosqlite.connect(self.db_path)
    
    async def setup_tables(self):
        """Initialize all database tables, now including the Recreation Repository."""
        try:
            async with self.get_connection() as conn:
                # --- Existing Tables ---
                await conn.execute('''CREATE TABLE IF NOT EXISTS gifts
                            (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, guild_id INTEGER, item_name TEXT, link TEXT, claimed_by INTEGER)''')
                
                await conn.execute('''CREATE TABLE IF NOT EXISTS ai_history
                            (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                             user_id INTEGER, 
                             guild_id INTEGER,
                             role TEXT, 
                             content TEXT, 
                             timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')
                
                # --- NEW: Games Repository ---
                # Status: 'seen', 'played', 'playing', 'wishlist'
                # Added: external_rating
                await conn.execute('''CREATE TABLE IF NOT EXISTS games
                            (id INTEGER PRIMARY KEY AUTOINCREMENT,
                             title TEXT,
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
                             guild_id INTEGER,
                             created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                             UNIQUE(title, guild_id))''')

                # --- NEW: Ratings/Votes ---
                # One rating per user per game per server
                await conn.execute('''CREATE TABLE IF NOT EXISTS game_ratings
                            (game_id INTEGER,
                             user_id INTEGER,
                             guild_id INTEGER,
                             rating INTEGER CHECK(rating >= 1 AND rating <= 10),
                             PRIMARY KEY (game_id, user_id, guild_id),
                             FOREIGN KEY(game_id) REFERENCES games(id) ON DELETE CASCADE)''')

                # --- NEW: Tagging System (Normalized) ---
                # 1. Tags Table: Stores unique tag names
                await conn.execute('''CREATE TABLE IF NOT EXISTS tags
                            (id INTEGER PRIMARY KEY AUTOINCREMENT,
                             name TEXT,
                             guild_id INTEGER,
                             created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                             UNIQUE(name, guild_id))''')

                # 2. Game_Tags Table: Links Games to Tags via IDs
                await conn.execute('''CREATE TABLE IF NOT EXISTS game_tags
                            (game_id INTEGER,
                             tag_id INTEGER,
                             PRIMARY KEY (game_id, tag_id),
                             FOREIGN KEY(game_id) REFERENCES games(id) ON DELETE CASCADE,
                             FOREIGN KEY(tag_id) REFERENCES tags(id) ON DELETE CASCADE)''')
                
                await conn.commit()
            logger.info("Aperture Science Database Tables Initialized.")
        except Exception as e:
            logger.error(f"Database Initialization Failed: {e}")

    # --- Game Methods ---

    async def add_game(self, title: str, added_by: int, guild_id: int, tags: Optional[List[str]] = None, **kwargs) -> int:
        """Add a new simulation to the roster. Returns the new Game ID."""
        try:
            async with self.get_connection() as conn:
                # Dynamic query building based on provided kwargs
                columns = ['title', 'added_by', 'guild_id']
                values = [title, added_by, guild_id]
                placeholders = ['?', '?', '?']
                
                for key, value in kwargs.items():
                    if value is not None:
                        columns.append(key)
                        values.append(value)
                        placeholders.append('?')
                
                query = f"INSERT INTO games ({', '.join(columns)}) VALUES ({', '.join(placeholders)})"
                cursor = await conn.execute(query, values)
                game_id = cursor.lastrowid
                await conn.commit()
            
            # Handle tags if provided
            if tags and game_id:
                await self.add_tags(game_id, tags, guild_id)
                
            return game_id
        except aiosqlite.IntegrityError:
            logger.warning(f"Game '{title}' already exists in the repository.")
            return -1
        except Exception as e:
            logger.error(f"Failed to add game: {e}")
            return -1

    async def rate_game(self, game_id: int, user_id: int, guild_id: int, rating: int):
        """Submit a mandatory performance review for a simulation."""
        try:
            async with self.get_connection() as conn:
                await conn.execute("INSERT OR REPLACE INTO game_ratings (game_id, user_id, guild_id, rating) VALUES (?, ?, ?, ?)",
                          (game_id, user_id, guild_id, rating))
                await conn.commit()
        except Exception as e:
            logger.error(f"Rating failed: {e}")

    async def add_tags(self, game_id: int, tags: List[str], guild_id: int):
        """Attach classifiction tags to a game using the new normalized schema."""
        if not tags:
            return
            
        try:
            async with self.get_connection() as conn:
                for tag in tags:
                    tag_clean = tag.strip() # maintain case for display, but search might be case-insensitive? 
                    # Let's keep it simple: Store as provided, UNIQUE constraint might fail if casing differs?
                    # Best practice: Store normalized or handle "INSERT OR IGNORE" carefully.
                    # For now, we'll strip.
                    
                    # 1. Ensure tag exists in 'tags' table and get its ID
                    # We use INSERT OR IGNORE then a SELECT to handle concurrency/duplicates
                    await conn.execute("INSERT OR IGNORE INTO tags (name, guild_id) VALUES (?, ?)", (tag_clean, guild_id))
                    
                    # If it was ignored, we still need the ID.
                    async with conn.execute("SELECT id FROM tags WHERE name = ? AND guild_id = ?", (tag_clean, guild_id)) as cursor:
                        result = await cursor.fetchone()
                    
                    if result:
                        tag_id = result[0]
                        # 2. Link game to tag
                        await conn.execute("INSERT OR IGNORE INTO game_tags (game_id, tag_id) VALUES (?, ?)", (game_id, tag_id))
                
                await conn.commit()
        except Exception as e:
            logger.error(f"Tagging failed: {e}")

    async def get_game_library(self, 
                         guild_id: int,
                         status_filter: Optional[str] = None, 
                         tag_filter: Optional[str] = None, 
                         player_count: Optional[int] = None,
                         release_state: Optional[str] = None) -> List[Dict]:
        """
        Retrieve the dossier of games with optional filtering.
        Returns a list of dictionaries containing game data + average rating.
        """
        try:
            async with self.get_connection() as conn:
                conn.row_factory = aiosqlite.Row # Allows accessing columns by name
                
                # Using basic concatenation for the JOIN condition parameter isn't standard SQL binding for identifiers or logic blocks unless we construct the string carefully.
                # However, we can simply bind the guild_id in the execute call.
                
                query = """
                    SELECT g.*, 
                           AVG(r.rating) as avg_rating,
                           GROUP_CONCAT(t.name, ', ') as tags
                    FROM games g
                    LEFT JOIN game_ratings r ON g.id = r.game_id
                    LEFT JOIN game_tags gt ON g.id = gt.game_id
                    LEFT JOIN tags t ON gt.tag_id = t.id
                    WHERE g.guild_id IN (?, 0)
                """
                
                params = [guild_id, guild_id] # Start with guild_id for WHERE IN clause (local, global are bound)
                # Note: SQLite IN (?, 0) naturally takes [guild_id], but let's bind explicitly to just be safe.
                # Actually, IN (?, 0) is static 0. We just need to pass `guild_id` once.
                params = [guild_id] 
                
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
                
                async with conn.execute(query, params) as cursor:
                    rows = await cursor.fetchall()
                
                # Convert aiosqlite.Row objects to real dicts
                return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Failed to fetch library: {e}")
            return []

    async def update_game(self, title: str, guild_id: int, **kwargs) -> bool:
        """
        Generic update method for game fields.
        Usage: db.update_game("Factorio", status="playing", min_players=10)
        """
        try:
            if not kwargs:
                return False
                
            async with self.get_connection() as conn:
                # Build the SET clause dynamically
                set_clauses = []
                values = []
                
                for key, value in kwargs.items():
                    if key == 'status':
                        value = value.lower()
                        
                    set_clauses.append(f"{key} = ?")
                    values.append(value)
                
                # Add the WHERE clause parameter
                values.extend([title, guild_id])
                
                query = f"UPDATE games SET {', '.join(set_clauses)} WHERE title = ? AND guild_id = ?"
                
                cursor = await conn.execute(query, values)
                success = cursor.rowcount > 0
                await conn.commit()
                
                return success
        except Exception as e:
            logger.error(f"Failed to update game {title}: {e}")
            return False

    async def search_game_titles(self, query: str, guild_id: int) -> List[str]:
        """Search game titles for autocomplete"""
        try:
            async with self.get_connection() as conn:
                async with conn.execute("SELECT title FROM games WHERE title LIKE ? AND guild_id IN (?, 0) LIMIT 25", (f'%{query}%', guild_id)) as cursor:
                    rows = await cursor.fetchall()
                return [r[0] for r in rows]
        except Exception as e:
            logger.error(f"Failed to search games: {e}")
            return []

    # --- AI History Methods (Kept from your original) ---
    async def add_ai_message(self, user_id: int, guild_id: int, role: str, content: str):
        try:
            async with self.get_connection() as conn:
                await conn.execute("INSERT INTO ai_history (user_id, guild_id, role, content) VALUES (?, ?, ?, ?)", (user_id, guild_id, role, content))
                await conn.commit()
        except Exception as e:
            logger.error(f"Failed to add AI message: {e}")

    async def get_ai_history(self, user_id: int, guild_id: Optional[int] = None, limit: int = 20) -> List[Tuple[str, str]]:
        try:
            async with self.get_connection() as conn:
                if guild_id is None:
                    # Global Context (All Servers)
                    async with conn.execute("SELECT role, content FROM ai_history WHERE user_id = ? ORDER BY id DESC LIMIT ?", (user_id, limit)) as cursor:
                        rows = await cursor.fetchall()
                else:
                    # Local Context (Specific Server)
                    async with conn.execute("SELECT role, content FROM ai_history WHERE user_id = ? AND guild_id = ? ORDER BY id DESC LIMIT ?", (user_id, guild_id, limit)) as cursor:
                        rows = await cursor.fetchall()
                
                return list(reversed(rows))
        except Exception as e:
            logger.error(f"Failed to get AI history: {e}")
            return []

    async def clear_ai_history(self, user_id: int):
        try:
            async with self.get_connection() as conn:
                await conn.execute("DELETE FROM ai_history WHERE user_id = ?", (user_id,))
                await conn.commit()
        except Exception as e:
            logger.error(f"Failed to clear AI history: {e}")

    async def get_tags(self, guild_id: int) -> List[str]:
        try:
            async with self.get_connection() as conn:
                # Get tags across both scopes
                async with conn.execute("SELECT DISTINCT name FROM tags WHERE guild_id IN (?, 0) ORDER BY name ASC", (guild_id,)) as cursor:
                    rows = await cursor.fetchall()
                return [r[0] for r in rows]
        except Exception as e:
            logger.error(f"Failed to get tags: {e}")
            return []

    async def recommend_games(self, guild_id: int, min_players: int = 0, tag: Optional[str] = None, limit: int = 5) -> str:
        """
        Searches the DB and returns a formatted string for the AI to read.
        """
        try:
            async with self.get_connection() as conn:
                conn.row_factory = aiosqlite.Row
                
                query = "SELECT title, min_players, max_players, notes FROM games WHERE guild_id IN (?, 0)"
                params = [guild_id]
                
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
                
                async with conn.execute(query, params) as cursor:
                    rows = await cursor.fetchall()
                
                if not rows:
                    return "DATABASE QUERY RESULT: No simulations found matching those criteria."
                
                # Format this into a string the AI can read
                result_text = "DATABASE QUERY RESULT (Cave Johnson's Approved List):\n"
                for row in rows:
                    result_text += f"- {row['title']} (Players: {row['min_players']}-{row['max_players']}). Note: {row['notes']}\n"
                
                return result_text
                
        except Exception as e:
            import traceback
            with open("trace.txt", "w") as f:
                traceback.print_exc(file=f)
            logger.error(f"Recommendation failed: {e}")
            return "DATABASE ERROR: The file cabinets are jammed."
