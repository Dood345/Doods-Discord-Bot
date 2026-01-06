"""Game-related commands for the Discord bot - Powered by Aperture Science"""

import discord
from discord import app_commands
from discord.ext import commands
import logging
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
        titles = self.db.search_game_titles(current)
        return [app_commands.Choice(name=title, value=title) for title in titles]

    @game_group.command(name="add", description="Submit a new mandatory fun module (simulation)")
    async def add_game(self, interaction: discord.Interaction, title: str, link: str, min_players: int, max_players: int):
        """Add a game to the library"""
        await interaction.response.defer()
        
        # Add to database
        game_id = self.db.add_game(
            title=title, 
            added_by=interaction.user.id, 
            min_players=min_players, 
            max_players=max_players, 
            store_link=link
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
        games = self.db.search_game_titles(title_search)
        if title_search not in games:
             await interaction.followup.send(
                f"🎙️ **Cave Johnson here.** Error. Simulation **{title_search}** not found. "
                "Are you hallucinating again? I told them to fix the gas leak in the break room.",
                ephemeral=True
            )
             return

        # Get ID (a bit inefficient but works for now without complex lookup)
        # In a real app we'd map name->id in autocomplete or do a fetch, 
        # but since we just have the name from autocomplete, we assume it's valid if found.
        # We need the ID for the rating table.
        # Let's fetch the game details to get ID.
        library = self.db.get_game_library() 
        game = next((g for g in library if g['title'] == title_search), None)
        
        if game:
            self.db.rate_game(game['id'], interaction.user.id, score)
            await interaction.followup.send(
                f"🎙️ **Cave Johnson here.** Rating logged for **{title_search}**. "
                f"You gave it a **{score}/10**. Your opinion has been noted and likely discarded by a computer. "
                "Get back to work."
            )
        else:
             await interaction.followup.send("🎙️ **System Error.** Simulation data corrupted. Blame the Lab Boys.")

    @game_group.command(name="list", description="View the dossier of available simulations")
    @app_commands.choices(status_filter=[
        app_commands.Choice(name="Seen", value="seen"),
        app_commands.Choice(name="Playing", value="playing"),
        app_commands.Choice(name="Played", value="played")
    ])
    async def list_games(self, interaction: discord.Interaction, status_filter:  app_commands.Choice[str] = None):
        """List all games"""
        await interaction.response.defer()
        
        filter_val = status_filter.value if status_filter else None
        games = self.db.get_game_library(status_filter=filter_val)
        
        if not games:
            await interaction.followup.send("🎙️ **Cave Johnson here.** The filing cabinets are empty. "
                                            "Either we solved all of science, or someone stole the files. "
                                            "Start adding simulations!")
            return
            
        embed = discord.Embed(
            title="🔬 Aperture Science Mandatory Fun Modules",
            description=f"Status: **{filter_val.upper() if filter_val else 'ALL'}**\nTotal Simulations: {len(games)}",
            color=0xFFA500 # Aperture Orange
        )
        
        # Group by status if no filter
        if not filter_val:
            for status in ["playing", "seen", "played"]:
                status_games = [g for g in games if g['status'] == status]
                if status_games:
                    field_value = ""
                    for game in status_games:
                         rating = f"{game['avg_rating']:.1f}" if game['avg_rating'] else "N/A"
                         field_value += f"• **{game['title']}** - {rating}/10 Science Points\n"
                    
                    if len(field_value) > 1024: field_value = field_value[:1020] + "..."
                    embed.add_field(name=f"📂 {status.title()}", value=field_value, inline=False)
        else:
            # Simple list if filtered
            field_value = ""
            for game in games:
                rating = f"{game['avg_rating']:.1f}" if game['avg_rating'] else "N/A"
                field_value += f"• **{game['title']}** - {rating}/10 Science Points\n"
            
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

        success = self.db.update_game(title_search, **updates)
        
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