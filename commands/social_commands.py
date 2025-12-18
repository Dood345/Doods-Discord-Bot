"""Social interaction commands for the Discord bot"""

import discord
from discord import app_commands
from discord.ext import commands
import random
import logging

logger = logging.getLogger(__name__)

class SocialCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.config = bot.config
        self.ai_handler = bot.ai_handler
    
    def _get_random_character(self):
        """Get a random character for roasts/compliments"""
        characters = list(self.config.CHARACTER_INFO.keys())
        # Remove alexjones from general rotation (too intense for regular roasts)
        if 'alexjones' in characters:
            characters.remove('alexjones')
        return random.choice(characters)
    
    @app_commands.command(name='roast', description="Roast a server member")
    async def roast_member(self, interaction: discord.Interaction, member: discord.Member = None):
        """Roast a server member (or yourself if no one specified)"""
        await interaction.response.defer()
        
        if member is None:
            member = interaction.user
        
        # Don't roast the bot itself
        if member == self.bot.user:
            await interaction.followup.send("🤖 Nice try, but I'm unroastable. I'm made of pure digital perfection!")
            return
        
        # Select random character
        character = self._get_random_character()
        char_info = self.config.CHARACTER_INFO[character]
        
        # Try AI first
        if self.ai_handler.is_available():
            ai_response = await self.ai_handler.get_roast_response(character, member.display_name)
            if ai_response:
                await interaction.followup.send(f"{member.mention} {char_info['name']}: {ai_response}")
                return
        
        # Fallback to template roasts
        fallback_roasts = {
            'hank': [
                "{user} probably uses charcoal instead of propane, I tell you what!",
                "{user}'s lawn maintenance skills are about as good as Bobby's interest in football.",
                "That {user} ain't right, I tell you what.",
                "{user} probably thinks butane is acceptable. Dang it!",
                "{user} would put ketchup on a perfectly good steak, I tell you what!"
            ],
            'dale': [
                "{user} is probably a government spy sent to monitor our propane usage!",
                "I've been watching {user}, and their behavior is... suspicious.",
                "{user} is exactly the type of person the shadow government would recruit!",
                "Don't trust {user} - they're probably working for Big Tech!",
                "{user} glows in the dark! Classic fed behavior!"
            ],
            'cartman': [
                "{user} is totally lame and not kewl like me!",
                "Seriously {user}, you guys are being super cereal right now.",
                "{user} probably doesn't even respect my authoritah!",
                "{user} is almost as lame as Kyle... ALMOST.",
                "Whatever {user}, I'm going home! This is weak!"
            ],
            'redgreen': [
                "{user} couldn't fix a problem with a whole roll of duct tape and a 2x4.",
                "If {user} was any more useless, they'd be a government program.",
                "{user} is living proof that duct tape can't fix stupid.",
                "{user} needs more help than a one-legged cat in a sandbox.",
                "{user} couldn't find their way out of a paper bag with a map and a flashlight."
            ],
            'trek': [
                "Captain, I'm detecting unusual stupidity readings from {user}.",
                "{user}'s intelligence levels are... illogical, Captain.",
                "Computer analysis shows {user} is operating at 12% mental capacity.",
                "{user} appears to be suffering from a severe logic malfunction.",
                "Warning: {user} is emitting high levels of derp particles."
            ],
            'snake': [
                "{user} would blow their cover in the first 30 seconds of a stealth mission.",
                "I've seen cardboard boxes with better tactical awareness than {user}.",
                "{user} is the kind of soldier who would set off every alarm in Shadow Moses.",
                "Metal Gear?! More like {user} Gear - completely useless!",
                "{user} couldn't sneak past a sleeping guard dog."
            ],
            'kratos': [
                "{user} possesses all the combat prowess of a frightened sparrow.",
                "The gods themselves mock {user}'s pitiful existence.",
                "{user} would not survive one day in Sparta.",
                "I have seen more courage in a newborn than in {user}.",
                "{user}'s weakness brings shame to all mortals."
            ],
            'dante': [
                "{user} has reserved a special place in the circle of incompetence.",
                "In Hell's hierarchy, {user} ranks below the indecisive.",
                "{user}'s sins include crimes against intelligence itself.",
                "Even the damned point and laugh at {user}.",
                "{user} would get lost trying to find their way out of Limbo."
            ]
        }
        
        roasts = fallback_roasts.get(character, ["{user} is... special."])
        roast = random.choice(roasts).format(user=member.mention)
        await interaction.followup.send(f"{char_info['name']}: {roast}")
    
    @app_commands.command(name='compliment', description="Give someone a compliment")
    async def compliment_member(self, interaction: discord.Interaction, member: discord.Member = None):
        """Give someone a compliment (because we're not all mean!)"""
        await interaction.response.defer()

        if member is None:
            member = interaction.user
        
        if member == self.bot.user:
            await interaction.followup.send("🤖 Aww, thanks! You're pretty great yourself!")
            return
        
        # Select random character
        character = self._get_random_character()
        char_info = self.config.CHARACTER_INFO[character]
        
        # Try AI first
        if self.ai_handler.is_available():
            ai_response = await self.ai_handler.get_compliment_response(character, member.display_name)
            if ai_response:
                await interaction.followup.send(f"{char_info['name']}: {ai_response}")
                return
        
        # Fallback compliments
        fallback_compliments = {
            'hank': [
                "{user} is a fine, upstanding citizen, I tell you what. Probably uses propane.",
                "That {user} has a good head on their shoulders. Solid handshake, too.",
                "I'd trust {user} to watch my lawn. That's high praise."
            ],
            'dale': [
                "{user} is one of the few who's truly awake. Keep your eyes open, friend.",
                "I'd trust {user} in my bunker. They've got the right kind of paranoia.",
                "Gih! {user} has the tactical awareness to spot a black helicopter from a mile away."
            ],
            'cartman': [
                "You know what, {user}? You're... you're almost as cool as me. Almost.",
                "{user} isn't a total butthole, which is pretty rare. Respect.",
                "Okay, fine, {user} is pretty kewl. But I'm still the boss."
            ],
            'redgreen': [
                "{user} is more useful than a roll of duct tape at a family reunion.",
                "If {user} was a tool, they'd be the whole toolbox. Keep your stick on the ice.",
                "That {user} is as reliable as a '78 pickup truck held together with hope and zip ties."
            ],
            'trek': [
                "Fascinating. {user}'s logic and efficiency are highly commendable.",
                "{user}'s contributions to this crew are... significant. Well done.",
                "The cognitive readings from {user} are off the charts, Captain. In a good way."
            ],
            'snake': [
                "{user} has the instincts of a true soldier. I'd have them on my team.",
                "Good situational awareness, {user}. You'd do well in the field.",
                "You've got potential, {user}. Don't waste it."
            ],
            'kratos': [
                "Hmph. {user} fights with honor. A rare quality.",
                "You have the spirit of a true warrior, {user}. Do not let the gods break it.",
                "BOY. Learn from {user}. They know strength."
            ],
            'dante': [
                "{user} walks a righteous path. May it lead you from the darkness.",
                "There is a light of virtue in {user} that even the damned can see.",
                "The soul of {user} shines with a hope for redemption."
            ]
        }
        
        compliments = fallback_compliments.get(character, ["{user} is pretty cool, I guess."])
        compliment = random.choice(compliments).format(user=member.display_name)
        await interaction.followup.send(f"{char_info['name']}: {compliment}")
    
    @app_commands.command(name='roastme', description="Roast yourself")
    async def roast_self(self, interaction: discord.Interaction):
        """Roast yourself, you masochist"""
        # Forward to main roast function
        await self.roast_member(interaction, interaction.user)

async def setup(bot):
    await bot.add_cog(SocialCommands(bot))