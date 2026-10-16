"""Character-based commands for the Discord bot.

Characters come from content/personas.json (bot.config.PERSONAS). /ask covers all of them;
the per-character commands below are kept as aliases.
"""

import discord
from discord import app_commands
from discord.ext import commands
import random
import logging
from datetime import timedelta
from typing import List

from services.debate_service import DebateService

logger = logging.getLogger(__name__)

class CharacterCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.config = bot.config
        self.ai_handler = bot.ai_handler
        self.debates = DebateService(bot.ai_handler, bot.config.PERSONAS)

    async def _get_character_response(self, character: str, user_input: str = None):
        """Get a response from a character, AI first then fallback"""
        if user_input and self.ai_handler.is_available():
            ai_response = await self.ai_handler.get_character_response(character, user_input)
            if ai_response:
                return ai_response

        # Fallback to static JSON quotes organized by character
        return self.bot.dialogue.get(character, 'fallback', fallback="*character malfunctioned*")

    async def _respond(self, interaction: discord.Interaction, character: str, user_input: str = None):
        await interaction.response.defer()
        response = await self._get_character_response(character, user_input)
        await interaction.followup.send(f"{self.config.PERSONAS[character].label}: {response}")

    def find_persona(self, text: str):
        """Persona key for a key or display name typed by the user, or None."""
        text = text.strip().lower()
        if text in self.config.PERSONAS:
            return text
        return next((k for k, p in self.config.PERSONAS.items() if p.name.lower() == text), None)

    async def character_autocomplete(self, interaction: discord.Interaction, current: str) -> List[app_commands.Choice[str]]:
        current = current.lower()
        return [app_commands.Choice(name=f"{p.emoji} {p.name}: {p.description}"[:100], value=key)
                for key, p in self.config.PERSONAS.items()
                if current in key or current in p.name.lower()][:25]

    @app_commands.command(name='ask', description="Ask one of the facility's guest characters something")
    @app_commands.describe(character="Who to ask", prompt="What to ask them")
    @app_commands.autocomplete(character=character_autocomplete)
    async def ask_command(self, interaction: discord.Interaction, character: str, prompt: str = None):
        key = self.find_persona(character)
        if key is None:
            names = ", ".join(p.name for p in self.config.PERSONAS.values())
            await interaction.response.send_message(f"❓ Never heard of them. Try one of: {names}", ephemeral=True)
            return
        await self._respond(interaction, key, prompt)

    @app_commands.command(name='debate', description="Two characters argue a topic for 3 rounds, then the server votes")
    @app_commands.describe(character="First debater", topic="What they argue about",
                           opponent="Second debater (random if left out)")
    @app_commands.autocomplete(character=character_autocomplete, opponent=character_autocomplete)
    async def debate_command(self, interaction: discord.Interaction, character: str, topic: str, opponent: str = None):
        a = self.find_persona(character)
        b = self.find_persona(opponent) if opponent else (self.debates.pick_opponent(a) if a else None)
        if a is None or b is None:
            await interaction.response.send_message("❓ I need two real characters. Pick them from the list.", ephemeral=True)
            return
        if a == b:
            await interaction.response.send_message("🪞 A debate against yourself is called a diary.", ephemeral=True)
            return
        if not self.debates.try_start(interaction.channel_id):
            await interaction.response.send_message("🎤 A debate is already running in this channel.", ephemeral=True)
            return
        try:
            await interaction.response.defer()
            first, second = self.config.PERSONAS[a], self.config.PERSONAS[b]
            topic = " ".join(topic.split())[:200]
            await interaction.followup.send(
                f"🎤 **FACILITY SHOWDOWN** 🎤\n{first.label} vs {second.label}\n**Topic:** {topic}")
            spoken = 0
            async for speaker, line in self.debates.run(a, b, topic):
                await interaction.followup.send(f"{speaker.label}: {line}")
                spoken += 1
            if spoken < 2:
                await interaction.followup.send("⚠️ The debate collapsed before it started. The lab boys blame the AI core.")
                return
            poll = discord.Poll(question=f"Who won? {topic}"[:300], duration=timedelta(hours=1))
            for p in (first, second):
                poll.add_answer(text=p.name[:55], emoji=p.emoji)
            await interaction.followup.send(poll=poll)
        finally:
            self.debates.finish(interaction.channel_id)

    # --- Legacy per-character commands (aliases for /ask) ---

    @app_commands.command(name='hank', description="Get a Hank Hill response")
    async def hank_command(self, interaction: discord.Interaction, user_input: str = None):
        await self._respond(interaction, 'hank', user_input)

    @app_commands.command(name='dale', description="Dale Gribble conspiracy wisdom")
    async def dale_command(self, interaction: discord.Interaction, user_input: str = None):
        await self._respond(interaction, 'dale', user_input)

    @app_commands.command(name='propane', description="Sweet Lady Propane knowledge")
    async def propane_wisdom(self, interaction: discord.Interaction):
        facts = [
            "Propane burns clean with a blue flame!",
            "Butane is a bastard gas!",
            "Taste the meat, not the heat!",
            "That's a clean burning hell, I tell you what!",
            "I sell propane and propane accessories, I tell you what!",
            "Propane is the future, I tell you what!"
        ]
        await interaction.response.send_message(f"🔥 **Propane Fact:** {random.choice(facts)}")

    @app_commands.command(name='cartman', description="Cartman being Cartman")
    async def cartman_command(self, interaction: discord.Interaction, user_input: str = None):
        await self._respond(interaction, 'cartman', user_input)

    @app_commands.command(name='redgreen', description="Get Red Green's handy advice")
    async def red_green_command(self, interaction: discord.Interaction, problem: str = None):
        await self._respond(interaction, 'redgreen', problem)

    @app_commands.command(name='trek', description="Get a Star Trek technical solution")
    async def trek_command(self, interaction: discord.Interaction, problem: str = None):
        await self._respond(interaction, 'trek', problem)

    # ALEX JONES PARODY (keeps its own random-theory fallback)
    @app_commands.command(name='conspiracy', description="Generate a ridiculous conspiracy theory")
    async def conspiracy_command(self, interaction: discord.Interaction, topic: str = None):
        await interaction.response.defer()
        if topic and self.ai_handler.is_available():
            ai_response = await self.ai_handler.get_character_response('alexjones', topic)
            if ai_response:
                await interaction.followup.send(f"{self.config.PERSONAS['alexjones'].label}: {ai_response}")
                return

        # Fallback to static JSON generator
        subjects = ["The globalists", "The deep state", "The new world order", "The interdimensional vampires", "Big Pharma"]
        actions = ["are turning", "have infiltrated", "are controlling", "are putting chemicals in"]
        objects = ["the water supply", "the school lunches", "the 5G towers", "the birds", "our DNA"]
        reasons = ["to make us docile", "to create a one-world government", "to lower our testosterone", "to harvest our life-force", "to turn the frogs gay"]

        theory = self.bot.dialogue.get(
            'alexjones',
            'conspiracy',
            subject=random.choice(subjects),
            action=random.choice(actions),
            object=random.choice(objects),
            reason=random.choice(reasons)
        )
        await interaction.followup.send(f"🚨 **INFOWARS ALERT:** {theory}")

    @app_commands.command(name='snake', description="Solid Snake tactical wisdom")
    async def snake_command(self, interaction: discord.Interaction, user_input: str = None):
        await self._respond(interaction, 'snake', user_input)

    @app_commands.command(name='kratos', description="Kratos godly wisdom and rage")
    async def kratos_command(self, interaction: discord.Interaction, user_input: str = None):
        await self._respond(interaction, 'kratos', user_input)

    @app_commands.command(name='dante', description="Dante's wisdom from the depths of hell")
    async def dante_command(self, interaction: discord.Interaction, user_input: str = None):
        await self._respond(interaction, 'dante', user_input)

    # TERMINATOR
    @app_commands.command(name='terminate', description="Terminator threat assessment")
    async def threat_assessment(self, interaction: discord.Interaction, target: str = None):
        if target:
            threat_levels = ["LOW", "MODERATE", "HIGH", "EXTREME", "DOES NOT COMPUTE"]
            recommendations = ['TERMINATE', 'MONITOR', 'IGNORE', 'OFFER BEER', 'RECRUIT FOR RESISTANCE']
            threat_level = random.choice(threat_levels)
            recommendation = random.choice(recommendations)

            await interaction.response.send_message(f"🤖 **THREAT ASSESSMENT:** {target.upper()}\n**THREAT LEVEL:** {threat_level}\n**RECOMMENDATION:** {recommendation}")
        else:
            await interaction.response.send_message("🤖 **T-800:** I need your clothes, your boots, and your motorcycle.")


async def setup(bot):
    await bot.add_cog(CharacterCommands(bot))
