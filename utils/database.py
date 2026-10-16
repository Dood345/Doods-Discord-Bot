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

                # Rolling summary of each user's older chat (everything up to last_id)
                await conn.execute('''CREATE TABLE IF NOT EXISTS ai_summaries
                            (user_id INTEGER PRIMARY KEY,
                             summary TEXT,
                             last_id INTEGER,
                             updated_at DATETIME DEFAULT CURRENT_TIMESTAMP)''')

                # Embedded old chat exchanges for recall (history_id = the user message's ai_history id)
                await conn.execute('''CREATE TABLE IF NOT EXISTS ai_embeddings
                            (history_id INTEGER PRIMARY KEY,
                             user_id INTEGER,
                             text TEXT,
                             vector BLOB)''')
                await conn.execute("CREATE INDEX IF NOT EXISTS idx_ai_embeddings_user ON ai_embeddings (user_id)")

                # Long-term facts a user asked Cave to remember (global per user, like ai_history)
                await conn.execute('''CREATE TABLE IF NOT EXISTS user_facts
                            (id INTEGER PRIMARY KEY AUTOINCREMENT,
                             user_id INTEGER,
                             fact TEXT,
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
                
                # Base games (guild_id 0) are shared, but ratings and tags are per server:
                # only count this server's ratings and show this server's (or base) tags.
                # Subqueries also avoid the ratings x tags join duplicating tag names.
                query = """
                    SELECT g.*,
                           (SELECT AVG(r.rating) FROM game_ratings r
                             WHERE r.game_id = g.id AND r.guild_id = ?) AS avg_rating,
                           (SELECT GROUP_CONCAT(t.name, ', ') FROM game_tags gt JOIN tags t ON gt.tag_id = t.id
                             WHERE gt.game_id = g.id AND t.guild_id IN (?, 0)) AS tags
                    FROM games g
                    WHERE g.guild_id IN (?, 0)
                """
                params = [guild_id, guild_id, guild_id]

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
                    # Subquery to find games linked to a tag with similar name (this server's or base tags)
                    query += """ AND g.id IN (
                        SELECT gt.game_id 
                        FROM game_tags gt 
                        JOIN tags t ON gt.tag_id = t.id 
                        WHERE t.name LIKE ? AND t.guild_id IN (?, 0)
                    )"""
                    params.extend([f"%{tag_filter}%", guild_id])
                
                query += " ORDER BY g.title ASC"
                
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
                await conn.execute("DELETE FROM ai_summaries WHERE user_id = ?", (user_id,))
                await conn.execute("DELETE FROM ai_embeddings WHERE user_id = ?", (user_id,))
                await conn.commit()
        except Exception as e:
            logger.error(f"Failed to clear AI history: {e}")

    # --- Embedded chat for recall ---
    async def get_last_embedded_id(self, user_id: int) -> int:
        try:
            async with self.get_connection() as conn:
                async with conn.execute("SELECT MAX(history_id) FROM ai_embeddings WHERE user_id = ?", (user_id,)) as cursor:
                    row = await cursor.fetchone()
            return row[0] or 0
        except Exception as e:
            logger.error(f"Failed to get last embedded id: {e}")
            return 0

    async def add_embeddings(self, user_id: int, items: List[Tuple[int, str, bytes]]):
        """Store (history_id, text, vector) rows for a user."""
        try:
            async with self.get_connection() as conn:
                # Skip rows whose history was wiped (/clearhistory) while they were being embedded
                await conn.executemany(
                    "INSERT OR REPLACE INTO ai_embeddings (history_id, user_id, text, vector) "
                    "SELECT ?, ?, ?, ? WHERE EXISTS (SELECT 1 FROM ai_history WHERE id = ?)",
                    [(hid, user_id, text, vec, hid) for hid, text, vec in items])
                await conn.commit()
        except Exception as e:
            logger.error(f"Failed to store embeddings: {e}")

    async def get_embeddings(self, user_id: int) -> List[Tuple[int, str, bytes]]:
        try:
            async with self.get_connection() as conn:
                async with conn.execute("SELECT history_id, text, vector FROM ai_embeddings WHERE user_id = ?", (user_id,)) as cursor:
                    return list(await cursor.fetchall())
        except Exception as e:
            logger.error(f"Failed to get embeddings: {e}")
            return []

    # --- Rolling chat summaries ---
    async def get_ai_summary(self, user_id: int) -> Tuple[Optional[str], int]:
        """(summary, last summarized ai_history id); (None, 0) if none yet."""
        try:
            async with self.get_connection() as conn:
                async with conn.execute("SELECT summary, last_id FROM ai_summaries WHERE user_id = ?", (user_id,)) as cursor:
                    row = await cursor.fetchone()
            return (row[0], row[1]) if row else (None, 0)
        except Exception as e:
            logger.error(f"Failed to get AI summary: {e}")
            return None, 0

    async def get_unsummarized_history(self, user_id: int, after_id: int, keep_recent: int) -> List[Tuple[int, str, str]]:
        """(id, role, content) rows newer than after_id, excluding the newest keep_recent rows."""
        try:
            async with self.get_connection() as conn:
                async with conn.execute(
                    "SELECT id, role, content FROM ai_history WHERE user_id = ? AND id > ? ORDER BY id DESC LIMIT -1 OFFSET ?",
                    (user_id, after_id, keep_recent)) as cursor:
                    rows = await cursor.fetchall()
            return list(reversed(rows))
        except Exception as e:
            logger.error(f"Failed to get unsummarized history: {e}")
            return []

    async def set_ai_summary(self, user_id: int, summary: str, last_id: int):
        try:
            async with self.get_connection() as conn:
                await conn.execute(
                    "INSERT OR REPLACE INTO ai_summaries (user_id, summary, last_id, updated_at) VALUES (?, ?, ?, CURRENT_TIMESTAMP)",
                    (user_id, summary, last_id))
                await conn.commit()
        except Exception as e:
            logger.error(f"Failed to save AI summary: {e}")

    # --- Long-term user facts ---
    MAX_USER_FACTS = 20
    MAX_FACT_LENGTH = 200

    async def add_user_fact(self, user_id: int, fact: str) -> str:
        """Store a fact for a user. Returns 'added', 'duplicate', 'full' or 'error'."""
        fact = " ".join(fact.split())[:self.MAX_FACT_LENGTH]
        if not fact:
            return "error"
        try:
            async with self.get_connection() as conn:
                async with conn.execute("SELECT fact FROM user_facts WHERE user_id = ?", (user_id,)) as cursor:
                    existing = [r[0].lower() for r in await cursor.fetchall()]
                if fact.lower() in existing:
                    return "duplicate"
                if len(existing) >= self.MAX_USER_FACTS:
                    return "full"
                await conn.execute("INSERT INTO user_facts (user_id, fact) VALUES (?, ?)", (user_id, fact))
                await conn.commit()
                return "added"
        except Exception as e:
            logger.error(f"Failed to add user fact: {e}")
            return "error"

    async def get_user_facts(self, user_id: int) -> List[str]:
        try:
            async with self.get_connection() as conn:
                async with conn.execute("SELECT fact FROM user_facts WHERE user_id = ? ORDER BY id", (user_id,)) as cursor:
                    return [r[0] for r in await cursor.fetchall()]
        except Exception as e:
            logger.error(f"Failed to get user facts: {e}")
            return []

    async def clear_user_facts(self, user_id: int):
        try:
            async with self.get_connection() as conn:
                await conn.execute("DELETE FROM user_facts WHERE user_id = ?", (user_id,))
                await conn.commit()
        except Exception as e:
            logger.error(f"Failed to clear user facts: {e}")

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
                        WHERE t.name LIKE ? AND t.guild_id IN (?, 0)
                    )"""
                    params.extend([f"%{tag}%", guild_id])
                
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
            logger.exception(f"Recommendation failed: {e}")
            return "DATABASE ERROR: The file cabinets are jammed."
