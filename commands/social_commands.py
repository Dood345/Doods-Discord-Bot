"""Social interaction commands for the Discord bot"""

import discord
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
    
    @commands.command(name='roast')
    async def roast_member(self, ctx, member: discord.Member = None):
        """Roast a server member (or yourself if no one specified)"""
        if member is None:
            member = ctx.author
        
        # Don't roast the bot itself
        if member == bot.user:
            await ctx.send("🤖 Nice try, but I'm unroastable. I'm made of pure digital perfection!")
            return
        
        # Select random character
        character = self._get_random_character()
        char_info = self.config.CHARACTER_INFO[character]
        
        # Try AI first
        if self.ai_handler.is_available():
            ai_response = await self.ai_handler.get_roast_response(character, member.display_name)
            if ai_response:
                await ctx.send(f"{char_info['name']}: {ai_response}")
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
        roast = random.choice(roasts).format(user=member.display_name)
        await ctx.send(f"{char_info['name']}: {roast}")
    
    @commands.command(name='compliment')
    async def compliment_member(self, ctx, member: discord.Member = None):
        """Give someone a compliment (because we're not all mean!)"""
        if member is None:
            member = ctx.author
        
        if member == self.bot.user:
            await ctx.send("🤖 Aww, thanks! You're pretty great yourself!")
            return
        
        # Select random character
        character = self._get_random_character()
        char_info = self.config.CHARACTER_INFO[character]
        
        # Try AI first
        if self.ai_handler.is_available():
            ai_response = await self.ai_handler.get_compliment_response(character, member.display_name)
            if ai_response:
                await ctx.send(f"{char_info['name']}: {ai_response}")
                return
        
        # Fallback compliments
        fallback_compliments = [
            f"{member.display_name} is cooler than the other side of the pillow!",
            f"{member.display_name} could survive a zombie apocalypse with just their wit!",
            f"{member.display_name} makes Hank Hill proud with their propane enthusiasm!",
            f"{member.display_name} is the kind of person Red Green would trust with his duct tape!",
            f"{member.display_name} has more game than a GameStop!",
            f"{member.display_name} is like pizza - even when they're bad, they're still pretty good!",
            f"{member.display_name} could probably talk their way out of a Predator hunt!",
            f"{member.display_name} has the tactical awareness of Solid Snake!",
            f"{member.display_name} possesses the wisdom to avoid all nine circles of hell!",
            f"{member.display_name} has the strength and honor that would make Kratos nod in approval!"
        ]
        
        await ctx.send(f"✨ {random.choice(fallback_compliments)}")
    
    @commands.command(name='roastme')
    async def roast_self(self, ctx):
        """Roast yourself, you masochist"""
        await self.roast_member(ctx, ctx.author)

async def setup(bot):
    await bot.add_cog(SocialCommands(bot))