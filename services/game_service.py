import logging
from typing import List, Tuple, Optional, Dict, Any

logger = logging.getLogger(__name__)

class GameService:
    """Service layer for handling game registry and library logic."""
    
    def __init__(self, db):
        self.db = db

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
            return True, (
                f"🎙️ **Cave Johnson here.** We've secured a new simulation: **{title}**. "
                "Try not to break it. Actually, break it. That's what we pay you for. "
                "We don't pay you? Right. Carry on."
            )
        else:
            return False, (
                f"🎙️ **Cave Johnson here.** Administrative sabotage! "
                f"The file for **{title}** already exists. "
                "Someone in filing is getting fired. Out of a cannon. Into the sun."
            )

    async def rate_game(self, title_search: str, score: int, user_id: int, guild_id: int) -> Tuple[bool, str]:
        """Validate and rate a game, returning the formatted message."""
        if score < 1 or score > 10:
            if score == 11:
                return False, "🎙️ **Cave Johnson here.** I see you selected 11. Listen, I like the enthusiasm, but the scale ends at 10. It's basic math. If you can't count to 10, don't touch the equipment."
            else:
                return False, "🎙️ **Cave Johnson here.** The rating scale is 1 to 10. Not zero, not negative five, not a billion. Follow instructions or you'll be demoted to 'Test Subject Class C'."

        games = await self.db.search_game_titles(title_search, guild_id)
        if title_search not in games:
             return False, f"🎙️ **Cave Johnson here.** Error. Simulation **{title_search}** not found. Are you hallucinating again? I told them to fix the gas leak in the break room."

        library = await self.db.get_game_library(guild_id) 
        game = next((g for g in library if g['title'] == title_search), None)
        
        if game:
            await self.db.rate_game(game['id'], user_id, guild_id, score)
            return True, f"🎙️ **Cave Johnson here.** Rating logged for **{title_search}**. You gave it a **{score}/10**. Your opinion has been noted and likely discarded by a computer. Get back to work."
        else:
            return False, "🎙️ **System Error.** Simulation data corrupted. Blame the Lab Boys."

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
             return False, "🎙️ **Cave Johnson here.** You called the update protocol but didn't change anything. Are you testing ME? Stop wasting science time."

        success = await self.db.update_game(title_search, guild_id, **updates)
        
        if success:
             changes = ", ".join(updates.keys())
             new_title = updates.get('title', title_search)
             return True, (
                f"🎙️ **Cave Johnson here.** Protocol **{new_title}** updated. "
                f"Amended fields: **{changes}**. "
                "The lab boys are filing the paperwork. By which I mean they're shredding the old files."
            )
        else:
             return False, (
                f"🎙️ **Cave Johnson here.** Failed to update **{title_search}**. "
                "It's either locked, missing, or you're spelling it wrong. "
                "Try hitting the screen harder. That usually works."
            )
