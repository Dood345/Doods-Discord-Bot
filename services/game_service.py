import logging
from typing import List, Tuple, Optional, Dict, Any

logger = logging.getLogger(__name__)

class GameService:
    """Service layer for handling game registry and library logic."""
    
    def __init__(self, db, dialogue_manager):
        self.db = db
        self.dialogue = dialogue_manager

    async def search_game_titles(self, current: str, guild_id: int) -> List[str]:
        return await self.db.search_game_titles(current, guild_id)

    async def get_filtered_tags(self, current: str, guild_id: int) -> List[str]:
        tags = await self.db.get_tags(guild_id)
        return [t for t in tags if current.lower() in t.lower()]

    async def get_comma_separated_tags(self, current: str, guild_id: int) -> List[Tuple[str, str]]:
        all_tags = await self.db.get_tags(guild_id)
        
        if ',' in current:
            prefix, sep, search_term = current.rpartition(',')
            prefix += sep + " "
            search_term = search_term.strip()
        else:
            prefix = ""
            search_term = current.strip()

        filtered = [t for t in all_tags if search_term.lower() in t.lower()]
        
        choices = []
        for t in filtered[:25]:
            display = f"{prefix}{t}"
            if len(display) > 100:
                display = display[:97] + "..."
            choices.append((display, display))
            
        return choices

    async def add_game(self, title: str, added_by: int, guild_id: int, 
                       min_players: int, max_players: int, **kwargs) -> Tuple[bool, str]:
        """Add a game to the database with optional parameters and return response text."""
        # Parse tags inside the service
        tags = kwargs.pop('tags', None)
        tag_list = [t.strip() for t in tags.split(',')] if tags else []
        
        game_id = await self.db.add_game(
            title=title, 
            added_by=added_by, 
            guild_id=guild_id,
            min_players=min_players, 
            max_players=max_players,
            tags=tag_list,
            **kwargs
        )
        
        if game_id != -1:
            msg = self.dialogue.get('cave_johnson', 'game_added_success', title=title)
            return True, msg
        else:
            msg = self.dialogue.get('cave_johnson', 'game_added_duplicate', title=title)
            return False, msg

    async def rate_game(self, title_search: str, score: int, user_id: int, guild_id: int) -> Tuple[bool, str]:
        """Validate and rate a game, returning the formatted message."""
        if score < 1 or score > 10:
            if score == 11:
                return False, self.dialogue.get('cave_johnson', 'game_rate_eleven')
            else:
                return False, self.dialogue.get('cave_johnson', 'game_rate_out_of_bounds')

        games = await self.db.search_game_titles(title_search, guild_id)
        if title_search not in games:
             return False, self.dialogue.get('cave_johnson', 'game_rate_not_found', title_search=title_search)

        library = await self.db.get_game_library(guild_id) 
        game = next((g for g in library if g['title'] == title_search), None)
        
        if game:
            await self.db.rate_game(game['id'], user_id, guild_id, score)
            msg = self.dialogue.get('cave_johnson', 'game_rate_success', title_search=title_search, score=score)
            return True, msg
        else:
            return False, self.dialogue.get('cave_johnson', 'system_error')

    async def get_library(self, guild_id: int, status_filter: str = None, tag_search: str = None, 
                          players: int = None, release_state: str = None) -> List[Dict]:
        """Fetch filtered game library."""
        return await self.db.get_game_library(
            guild_id=guild_id,
            status_filter=status_filter,
            tag_filter=tag_search,
            player_count=players,
            release_state=release_state
        )

    async def update_game(self, title_search: str, guild_id: int, updates: dict) -> Tuple[bool, str]:
        """Update game parameters and return success/format strings."""
        if not updates:
             return False, self.dialogue.get('cave_johnson', 'game_update_empty')

        success = await self.db.update_game(title_search, guild_id, **updates)
        
        if success:
             changes = ", ".join(updates.keys())
             new_title = updates.get('title', title_search)
             msg = self.dialogue.get('cave_johnson', 'game_update_success', new_title=new_title, changes=changes)
             return True, msg
        else:
             msg = self.dialogue.get('cave_johnson', 'game_update_fail', title_search=title_search)
             return False, msg
