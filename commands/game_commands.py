"""Game-related commands for the Discord bot - Powered by Aperture Science"""

import discord

from utils.layouts import game_library_card
from discord import app_commands
from discord.ext import commands
import logging
from typing import List

logger = logging.getLogger(__name__)

class GameCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.game_service = bot.game_service
        
    # Group for /game commands
    game_group = app_commands.Group(name="game", description="Manage the Aperture Science Testing Library")

    async def game_title_autocomplete(self, interaction: discord.Interaction, current: str) -> List[app_commands.Choice[str]]:
        """Autocomplete for game titles"""
        titles = await self.game_service.search_game_titles(current, interaction.guild_id)
        return [app_commands.Choice(name=title, value=title) for title in titles]

    async def tag_autocomplete(self, interaction: discord.Interaction, current: str) -> List[app_commands.Choice[str]]:
        """Autocomplete for tags"""
        filtered = await self.game_service.get_filtered_tags(current, interaction.guild_id)
        return [app_commands.Choice(name=t, value=t) for t in filtered[:25]]

    async def tags_autocomplete(self, interaction: discord.Interaction, current: str) -> List[app_commands.Choice[str]]:
        """Autocomplete for multiple comma-separated tags"""
        choices = await self.game_service.get_comma_separated_tags(current, interaction.guild_id)
        return [app_commands.Choice(name=name, value=value) for name, value in choices]

    @game_group.command(name="add", description="Submit a new mandatory fun module (simulation)")
    @app_commands.autocomplete(tags=tags_autocomplete)
    @app_commands.rename(
        min_players="min-players",
        max_players="max-players",
        ideal_players="ideal-players",
        release_state="release-state",
        external_rating="rating",
        link="store-link"
    )
    @app_commands.choices(status=[
        app_commands.Choice(name="Unknown", value="unknown"),
        app_commands.Choice(name="Playing", value="playing"),
        app_commands.Choice(name="Played", value="played"),
        app_commands.Choice(name="Wishlisted", value="wishlisted"),
        app_commands.Choice(name="Avoid", value="avoid")
    ])
    @app_commands.choices(release_state=[
        app_commands.Choice(name="TBA", value="TBA"),
        app_commands.Choice(name="Early Access", value="early access"),
        app_commands.Choice(name="Full Release", value="full release")
    ])
    @app_commands.describe(link="Steam or Epic store link: fills in title, players, tags and more automatically")
    async def add_game(self, interaction: discord.Interaction,
                       title: str = None,
                       min_players: int = None,
                       max_players: int = None,
                       link: str = None,
                       ideal_players: int = None,
                       status: app_commands.Choice[str] = None,
                       release_state: app_commands.Choice[str] = None,
                       external_rating: str = None,
                       tags: str = None,
                       notes: str = None,
                       category: str = None,
                       release_date: str = None):
        """Add a game to the library"""
        await interaction.response.defer()

        fields = dict(title=title, min_players=min_players, max_players=max_players,
                      release_state=release_state.value if release_state else None,
                      external_rating=external_rating, category=category, release_date=release_date, tags=tags)
        guessed_note = ""
        if link:
            filled = await self.game_service.details_from_link(link, **fields)
            if filled:
                if filled.pop("players_guessed", False) and min_players is None and max_players is None:
                    guessed_note = "\n-# Player count guessed from the store page; fix it with /game update."
                link = filled.pop("store_link")
                fields = filled
        if not fields.get("title"):
            await interaction.followup.send(
                "⚠️ Give me a title, or a Steam/Epic store link so I can fill it in myself.", ephemeral=True)
            return
        lo, hi = fields.pop("min_players") or 1, fields.pop("max_players") or 4

        success, message = await self.game_service.add_game(
            added_by=interaction.user.id, guild_id=interaction.guild_id,
            min_players=min(lo, hi), max_players=max(lo, hi), ideal_players=ideal_players,
            store_link=link, status=status.value if status else 'unknown', notes=notes, **fields
        )

        if success and link:
            details = [f"{min(lo, hi)}-{max(lo, hi)} players", fields.get("release_state"),
                       fields.get("external_rating"), fields.get("tags") and f"tags: {fields['tags']}"]
            message += "\n-# " + " · ".join(d for d in details if d) + guessed_note
        await interaction.followup.send(message)

    @game_group.command(name="rate", description="Rate a simulation's testing viability")
    @app_commands.autocomplete(title_search=game_title_autocomplete)
    async def rate_game(self, interaction: discord.Interaction, title_search: str, score: int):
        """Rate a game (1-10)"""
        await interaction.response.defer()
        success, message = await self.game_service.rate_game(
            title_search, score, interaction.user.id, interaction.guild_id
        )
        # Emulate the ephemeral warning behavior for rating scale and missing games
        if not success and (score < 1 or score > 10 or "not found" in message):
            await interaction.followup.send(message, ephemeral=True)
            return
            
        await interaction.followup.send(message)

    @game_group.command(name="list", description="View the dossier of available simulations")
    @app_commands.autocomplete(tag_search=tag_autocomplete)
    @app_commands.rename(
        tag_search="tag",
        players="players",
        release_state="release-state"
    )
    @app_commands.choices(status_filter=[
        app_commands.Choice(name="Unknown", value="unknown"),
        app_commands.Choice(name="Playing", value="playing"),
        app_commands.Choice(name="Played", value="played"),
        app_commands.Choice(name="Wishlisted", value="wishlisted"),
        app_commands.Choice(name="Avoid", value="avoid")
    ])
    @app_commands.choices(release_state=[
        app_commands.Choice(name="TBA", value="TBA"),
        app_commands.Choice(name="Early Access", value="early access"),
        app_commands.Choice(name="Full Release", value="full release")
    ])
    async def list_games(self, interaction: discord.Interaction, 
                         status_filter: app_commands.Choice[str] = None,
                         tag_search: str = None,
                         players: int = None,
                         release_state: app_commands.Choice[str] = None):
        """List all games with optional filtering"""
        await interaction.response.defer()
        
        status_val = status_filter.value if status_filter else None
        state_val = release_state.value if release_state else None
        
        # Async DB Call
        games = await self.game_service.get_library(
            guild_id=interaction.guild.id,
            status_filter=status_val,
            tag_search=tag_search,
            players=players,
            release_state=state_val
        )
        
        if not games:
            msg = self.bot.dialogue.get('cave_johnson', 'game_list_empty')
            await interaction.followup.send(msg)
            return
            
        desc = []
        if status_val: desc.append(f"Status: **{status_val.upper()}**")
        if state_val: desc.append(f"State: **{state_val.upper()}**")
        if tag_search: desc.append(f"Tag: **{tag_search}**")
        if players: desc.append(f"Player Count: **{players}**")
        
        card = game_library_card(games, desc, grouped=not status_val)
        await interaction.followup.send(view=card, allowed_mentions=discord.AllowedMentions.none())  # titles are user input

    @game_group.command(name="update", description="Modify a testing protocol (fill at least one field)")
    @app_commands.autocomplete(title_search=game_title_autocomplete)
    # 1. THE TRANSLATOR: Maps Python variables to cleaner Discord UI names
    @app_commands.rename(
        title_search="search",
        min_players="min-players",
        max_players="max-players",
        ideal_players="ideal-players",
        release_state="release-state",
        external_rating="rating",
        release_date="release-date",
        last_update="last-update",
        link="store-link"
    )
    @app_commands.choices(status=[
        app_commands.Choice(name="Unknown", value="unknown"),
        app_commands.Choice(name="Playing", value="playing"),
        app_commands.Choice(name="Played", value="played"),
        app_commands.Choice(name="Wishlisted", value="wishlisted"),
        app_commands.Choice(name="Avoid", value="avoid")
    ])
    @app_commands.choices(release_state=[
        app_commands.Choice(name="TBA", value="TBA"),
        app_commands.Choice(name="Early Access", value="early access"),
        app_commands.Choice(name="Full Release", value="full release")
    ])
    async def update_game(self, interaction: discord.Interaction, title_search: str,
                          # Identity
                          title: str = None,
                          category: str = None,
                          # Stats
                          min_players: int = None,
                          max_players: int = None,
                          ideal_players: int = None,
                          # Status & Meta
                          status: app_commands.Choice[str] = None,
                          release_state: app_commands.Choice[str] = None,
                          external_rating: str = None,
                          release_date: str = None,
                          last_update: str = None,
                          # Info
                          link: str = None,
                          notes: str = None):
        """Update game details"""
        await interaction.response.defer()
        
        updates = {}
        if title: updates['title'] = title
        if category: updates['category'] = category
        if min_players: updates['min_players'] = min_players
        if max_players: updates['max_players'] = max_players
        if ideal_players: updates['ideal_players'] = ideal_players
        if status: updates['status'] = status.value
        if release_state: updates['release_state'] = release_state.value
        if external_rating: updates['external_rating'] = external_rating
        if release_date: updates['release_date'] = release_date
        if last_update: updates['last_update'] = last_update
        if link: updates['store_link'] = link
        if notes: updates['notes'] = notes

        success, message = await self.game_service.update_game(
            title_search, interaction.guild_id, updates
        )
        
        if not success and "didn't change anything" in message:
             await interaction.followup.send(message, ephemeral=True)
             return
             
        await interaction.followup.send(message)

async def setup(bot):
    await bot.add_cog(GameCommands(bot))