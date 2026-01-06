"""Game-related commands for the Discord bot - Powered by Aperture Science"""

import discord
from discord import app_commands
from discord.ext import commands
import logging
import asyncio
from typing import List, Optional

logger = logging.getLogger(__name__)

class GameCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = bot.db
        
    # Group for /game commands
    game_group = app_commands.Group(name="game", description="Manage the Aperture Science Testing Library")

    async def game_title_autocomplete(self, interaction: discord.Interaction, current: str) -> List[app_commands.Choice[str]]:
        """Autocomplete for game titles"""
        titles = await asyncio.to_thread(self.db.search_game_titles, current)
        return [app_commands.Choice(name=title, value=title) for title in titles]

    @game_group.command(name="add", description="Submit a new mandatory fun module (simulation)")
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
    async def add_game(self, interaction: discord.Interaction, 
                       title: str, 
                       min_players: int, 
                       max_players: int,
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
        
        # Parse tags
        tag_list = [t.strip() for t in tags.split(',')] if tags else []

        # Add to database
        game_id = await asyncio.to_thread(
            self.db.add_game,
            title=title, 
            added_by=interaction.user.id, 
            min_players=min_players, 
            max_players=max_players,
            ideal_players=ideal_players,
            store_link=link,
            status=status.value if status else 'unknown',
            release_state=release_state.value if release_state else None,
            external_rating=external_rating,
            notes=notes,
            category=category,
            release_date=release_date,
            tags=tag_list
        )
        
        if game_id != -1:
            await interaction.followup.send(
                f"🎙️ **Cave Johnson here.** We've secured a new simulation: **{title}**. "
                "Try not to break it. Actually, break it. That's what we pay you for. "
                "We don't pay you? Right. Carry on."
            )
        else:
            await interaction.followup.send(
                f"🎙️ **Cave Johnson here.** Administrative sabotage! "
                f"The file for **{title}** already exists. "
                "Someone in filing is getting fired. Out of a cannon. Into the sun."
            )

    @game_group.command(name="rate", description="Rate a simulation's testing viability")
    @app_commands.autocomplete(title_search=game_title_autocomplete)
    async def rate_game(self, interaction: discord.Interaction, title_search: str, score: int):
        """Rate a game (1-10)"""
        # Check for integer incompetence
        if score < 1 or score > 10:
            if score == 11:
                await interaction.response.send_message(
                    "🎙️ **Cave Johnson here.** I see you selected 11. "
                    "Listen, I like the enthusiasm, but the scale ends at 10. "
                    "It's basic math. If you can't count to 10, don't touch the equipment.",
                    ephemeral=True
                )
            else:
                await interaction.response.send_message(
                    "🎙️ **Cave Johnson here.** The rating scale is 1 to 10. "
                    "Not zero, not negative five, not a billion. "
                    "Follow instructions or you'll be demoted to 'Test Subject Class C'.",
                    ephemeral=True
                )
            return

        await interaction.response.defer()
        
        # Check if game exists
        games = await asyncio.to_thread(self.db.search_game_titles, title_search)
        if title_search not in games:
             await interaction.followup.send(
                f"🎙️ **Cave Johnson here.** Error. Simulation **{title_search}** not found. "
                "Are you hallucinating again? I told them to fix the gas leak in the break room.",
                ephemeral=True
            )
             return

        # Get ID
        library = await asyncio.to_thread(self.db.get_game_library) 
        game = next((g for g in library if g['title'] == title_search), None)
        
        if game:
            await asyncio.to_thread(self.db.rate_game, game['id'], interaction.user.id, score)
            await interaction.followup.send(
                f"🎙️ **Cave Johnson here.** Rating logged for **{title_search}**. "
                f"You gave it a **{score}/10**. Your opinion has been noted and likely discarded by a computer. "
                "Get back to work."
            )
        else:
             await interaction.followup.send("🎙️ **System Error.** Simulation data corrupted. Blame the Lab Boys.")

    @game_group.command(name="list", description="View the dossier of available simulations")
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
        games = await asyncio.to_thread(
            self.db.get_game_library,
            status_filter=status_val,
            tag_filter=tag_search,
            player_count=players,
            release_state=state_val
        )
        
        if not games:
            await interaction.followup.send("🎙️ **Cave Johnson here.** The filing cabinets are empty. "
                                            "Either we solved all of science, or someone stole the files. "
                                            "Try loosening your search criteria.")
            return
            
        desc = []
        if status_val: desc.append(f"Status: **{status_val.upper()}**")
        if state_val: desc.append(f"State: **{state_val.upper()}**")
        if tag_search: desc.append(f"Tag: **{tag_search}**")
        if players: desc.append(f"Player Count: **{players}**")
        
        description = "\n".join(desc) + f"\nTotal Simulations: {len(games)}"
        
        embed = discord.Embed(
            title="🔬 Aperture Science Mandatory Fun Modules",
            description=description,
            color=0xFFA500 # Aperture Orange
        )
        
        # Helper to format game line
        def format_game(g):
            rating = f"{g['avg_rating']:.1f}" if g['avg_rating'] else "N/A"
            players = f"{g['min_players']}-{g['max_players']}"
            ideal = f" (Ideal: {g['ideal_players']})" if g['ideal_players'] else ""
            state = f"[{g['release_state']}]" if g['release_state'] else ""
            return f"• **{g['title']}** {state}\n  ╚ Rating: {rating}/10 | Players: {players}{ideal}"

        # Group by status if no status filter is applied
        if not status_val:
            for status in ["playing", "wishlisted", "unknown", "played", "avoid"]:
                status_games = [g for g in games if g['status'].lower() == status]
                if status_games:
                    field_value = ""
                    for game in status_games:
                         field_value += format_game(game) + "\n"
                    
                    if len(field_value) > 1024: field_value = field_value[:1020] + "..."
                    embed.add_field(name=f"📂 {status.title()}", value=field_value, inline=False)
        else:
            # Simple flat list if filtered by status
            field_value = ""
            for game in games:
                field_value += format_game(game) + "\n"
            
            if len(field_value) > 4000: field_value = field_value[:4000] + "..." # Description limit
            embed.description += "\n\n" + field_value

        embed.set_footer(text="Testing must continue indefinitely.")
        await interaction.followup.send(embed=embed)

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
        
        if not updates:
             await interaction.followup.send(
                f"🎙️ **Cave Johnson here.** You called the update protocol but didn't change anything. "
                "Are you testing ME? Stop wasting science time.",
                ephemeral=True
            )
             return

        success = await asyncio.to_thread(self.db.update_game, title_search, **updates)
        
        if success:
             changes = ", ".join(updates.keys())
             new_title = title if title else title_search
             await interaction.followup.send(
                f"🎙️ **Cave Johnson here.** Protocol **{new_title}** updated. "
                f"Amended fields: **{changes}**. "
                "The lab boys are filing the paperwork. By which I mean they're shredding the old files."
            )
        else:
             await interaction.followup.send(
                f"🎙️ **Cave Johnson here.** Failed to update **{title_search}**. "
                "It's either locked, missing, or you're spelling it wrong. "
                "Try hitting the screen harder. That usually works."
            )

async def setup(bot):
    await bot.add_cog(GameCommands(bot))