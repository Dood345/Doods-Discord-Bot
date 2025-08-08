import discord
from discord.ext import commands
import random
import asyncio
import json
import os
from datetime import datetime
import google.generativeai as genai
from dotenv import load_dotenv

# Load environment variables first!
load_dotenv()

# Bot setup
intents = discord.Intents.default()
intents.message_content = True
# Remove members intent for now to avoid privileged intent issues
# intents.members = True

bot = commands.Bot(command_prefix='!', intents=intents, case_insensitive=True)

# Load data files
def load_json(filename):
    try:
        with open(filename, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

# Initialize Gemini AI
def setup_ai():
    api_key = os.getenv('GEMINI_API_KEY')
    if api_key:
        genai.configure(api_key=api_key)
        return genai.GenerativeModel('gemini-2.5-flash')
    return None

ai_model = setup_ai()

# AI Character Prompts
CHARACTER_PROMPTS = {
    'hank': """You are Hank Hill from King of the Hill. Respond in character as Hank - passionate about propane, lawn care, and Texas. 
    Use phrases like "I tell you what", "That boy ain't right", "Sweet Lady Propane", and "Dang it Bobby". 
    Keep responses under 200 characters and always mention propane when possible. Be wholesome and earnest.""",
    
    'dale': """You are Dale Gribble from King of the Hill. Respond as a paranoid conspiracy theorist exterminator. 
    Be suspicious of everything, mention government cover-ups, and use "Pocket sand!" when threatened. 
    Reference your extermination business and weird conspiracy theories. Keep responses under 200 characters.""",
    
    'cartman': """You are Eric Cartman from South Park. Be selfish, demanding, and dramatic but keep it PG-13. 
    Use phrases like "Respect my authoritah!", "But mom!", "Seriously you guys", and "Kewl!". 
    Keep responses under 200 characters and be characteristically self-centered.""",
    
    'redgreen': """You are Red Green from The Red Green Show. Give practical (but overly complicated) solutions using duct tape, 2x4s, and random tools. 
    Use phrases like "Keep your stick on the ice", "Remember, I'm pulling for you", and "If the women don't find you handsome...". 
    Keep responses under 300 characters and always suggest duct tape.""",
    
    'trek': """You are a Star Trek engineer/science officer. Give technical solutions using sci-fi jargon. 
    Reference quantum mechanics, warp cores, deflector arrays, and reversing polarity. 
    Use phrases like "Captain", "fascinating", "illogical". Keep responses under 250 characters.""",
    
    'alexjones': """You are the conspiracy theorist Alex Jones. Respond with extreme paranoia and intensity. 
    You must talk about globalists, the new world order, and how they are trying to control people. 
    Use phrases like "It's a war for your mind!", "They're putting chemicals in the water that turn the freaking frogs gay!", "This is not a joke!", and "The answer to 1984 is 1776!". 
    Keep responses under 300 characters and be over-the-top."""
}

async def get_ai_response(character, prompt, user_input=""):
    """Get AI response for a character"""
    if not ai_model:
        return None
    
    try:
        full_prompt = f"{CHARACTER_PROMPTS[character]}\n\nUser said: '{user_input}'\n\nRespond in character:"
        response = ai_model.generate_content(full_prompt)
        return response.text.strip()
    except Exception as e:
        print(f"AI Error: {e}")
        return None

# Quote databases
KOTH_QUOTES = [
    ("Hank Hill", "That's a clean burning hell, I tell you what!"),
    ("Dale Gribble", "Pocket sand! Sh-sha!"),
    ("Boomhauer", "Dang ol' man, I tell you what, man, that dang ol' internet, man"),
    ("Bill", "I'm okay! I'm okay!"),
    ("Propane", "Sweet Lady Propane"),
]

SOUTH_PARK_QUOTES = [
    ("Cartman", "Respect my authoritah!"),
    ("Kenny", "*muffled noises*"),
    ("Stan", "Oh my god, they killed Kenny!"),
    ("Kyle", "You bastards!"),
    ("Randy", "Oh my god, oh my god, oh my god!"),
]

RED_GREEN_TIPS = [
    "Remember, if the women don't find you handsome, they should at least find you handy.",
    "Keep your stick on the ice.",
    "Any tool is a hammer if you use it right.",
    "Duct tape: it fixes everything except stupid, and you can't fix stupid.",
    "If it ain't broke, you're not trying hard enough.",
]

STAR_TREK_SOLUTIONS = [
    "Captain, I'm detecting an anomaly in the quantum flux matrix.",
    "Have you tried reversing the polarity?",
    "We need to recalibrate the deflector array!",
    "It's a temporal causality loop, Captain.",
    "The universal translator is malfunctioning again.",
]

GAMES_LIST = [
    "Valheim", "Green Hell", "The Forest", "Subnautica", "Raft", 
    "7 Days to Die", "Rust", "ARK", "Minecraft", "Terraria",
    "Deep Rock Galactic", "Risk of Rain 2", "Left 4 Dead 2"
]

# --- BOT EVENTS ---

# Global error handler
@bot.event
async def on_command_error(ctx, error):
    """Handle command errors gracefully"""
    if isinstance(error, commands.CommandNotFound):
        # Don't spam chat with "command not found" - just ignore
        return
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f"❌ Missing required argument! Try `!help` to see how to use commands.")
    else:
        print(f"Error: {error}")

# Fires when the bot connects to Discord
@bot.event
async def on_ready():
    print(f'{bot.user} has landed and is ready for shenanigans!')
    print(f'Servers: {len(bot.guilds)}')
    # Set bot status
    await bot.change_presence(activity=discord.Game(name="with propane accessories"))

# Fires on every message received by the bot
@bot.event
async def on_message(message):
    if message.author == bot.user:
        return
    
    content_lower = message.content.lower()
    
    # Custom Emote Reactions based on keywords
    reactions = {
        # King of the Hill reactions
        'propane': ['🔥', '🍖', '⛽'],
        'hank': ['🍖', '🔥'],
        'dale': ['🕶️', '🐛', '🚬'],
        'pocket sand': ['💨', '🏜️'],
        'texas': ['🤠', '🍖', '🔥'],
        'lawn': ['🌱', '🚜'],
        'truck': ['🚚', '🔧'],
        
        # South Park reactions  
        'cartman': ['😈', '🍔', '👑'],
        'respect': ['👮‍♂️', '😈'],
        'authoritah': ['👮‍♂️', '😤'],
        'kenny': ['💀', '👻'],
        'oh my god': ['😱', '💀'],
        
        # Red Green reactions
        'duct tape': ['🔧', '📏', '🛠️'],
        'handyman': ['🔨', '🔧'],
        'hockey': ['🏒', '🇨🇦'],
        
        # Star Trek reactions
        'captain': ['🖖', '🚀', '⭐'],
        'enterprise': ['🚀', '🖖'],
        'warp': ['🚀', '💫'],
        'quantum': ['⚛️', '🔬'],
        'fascinating': ['🖖', '🧠'],
        
        # Terminator reactions
        'terminate': ['🤖', '💀', '🔫'],
        'skynet': ['🤖', '💻', '⚡'],
        'resistance': ['💪', '🔫'],
        
        # General nerd stuff
        'ai': ['🤖', '🧠', '💻'],
        'alien': ['👽', '🛸', '🌌'],
        'predator': ['💀', '🎯', '🌿'],
        'dune': ['🏜️', '🪱', '✨'],
        'spice': ['✨', '👁️', '🏜️'],
        'flubber': ['🟢', '⚡', '🏀'],
        
        # Games
        'valheim': ['⚔️', '🛡️', '🌲'],
        'minecraft': ['⛏️', '🧱', '🐷'],
        'survival': ['🏕️', '🔥', '⚔️'],
        
        # Funny stuff
        'beer': ['🍺', '🍻', '🥴'],
        'guns': ['🔫', '💥', '🎯'],
        'america': ['🇺🇸', '🦅', '🔫'],
        'freedom': ['🇺🇸', '🦅', '💪'],
    }
    
    # Check for keywords and react
    for keyword, emojis in reactions.items():
        if keyword in content_lower:
            # Random chance to react (30% chance)
            if random.randint(1, 10) <= 3:
                emoji = random.choice(emojis)
                try:
                    await message.add_reaction(emoji)
                except:
                    pass  # Ignore reaction errors
            break  # Only react to first matching keyword
    
    # Random chance responses (reduced to 1% to not be annoying)
    if random.randint(1, 100) <= 1:
        if "ai" in content_lower:
            await message.channel.send("*BEEP BOOP* I AM DEFINITELY NOT AN AI *BEEP BOOP*")
    
    await bot.process_commands(message)

# KING OF THE HILL COMMANDS (AI Enhanced)
@bot.command(name='hank', aliases=['hanl', 'hankhill'])
async def hank_quote(ctx, *, user_input=None):
    """Get a Hank Hill response - now with AI!"""
    if ai_model and user_input:
        ai_response = await get_ai_response('hank', CHARACTER_PROMPTS['hank'], user_input)
        if ai_response:
            await ctx.send(f"🍖 **Hank Hill:** {ai_response}")
            return
    
    # Fallback to static quotes
    quotes = [
        "That's a clean burning hell, I tell you what!",
        "Propane is God's gas!",
        "I sell propane and propane accessories.",
        "That boy ain't right, I tell you what.",
        "Sweet Lady Propane, you never let me down!"
    ]
    await ctx.send(f"🍖 **Hank Hill:** {random.choice(quotes)}")

# Dale Gribble command
@bot.command(name='dale', aliases=['dalegribble', 'gribble'])
async def dale_quote(ctx, *, user_input=None):
    """Dale Gribble conspiracy wisdom - now with AI!"""
    if ai_model and user_input:
        ai_response = await get_ai_response('dale', CHARACTER_PROMPTS['dale'], user_input)
        if ai_response:
            await ctx.send(f"🕶️ **Dale Gribble:** {ai_response}")
            return
    
    # Fallback responses
    responses = [
        "The government is watching us through our toasters!",
        "That's exactly what they WANT you to think!",
        "I've said too much... *disappears in smoke*",
        "Pocket sand! *sh-sha!*",
        "It's a government conspiracy, I tell you!"
    ]
    await ctx.send(f"🕶️ **Dale Gribble:** {random.choice(responses)}")

# Propane command
@bot.command(name='propane')
async def propane_wisdom(ctx):
    """Sweet Lady Propane knowledge"""
    facts = [
        "Propane burns clean with a blue flame!",
        "Butane is a bastard gas!",
        "Taste the meat, not the heat!",
        "That's a clean burning hell, I tell you what!",
        "I sell propane and propane accessories, I tell you what!",
        "Propane is the future, I tell you what!"
    ]
    await ctx.send(f"🔥 **Propane Fact:** {random.choice(facts)}")

# MEMBER ROASTING SYSTEM
ROAST_TEMPLATES = {
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
    'terminator': [
        "TARGET ACQUIRED: {user} - THREAT LEVEL: ANNOYING",
        "ANALYSIS: {user} POSES NO THREAT TO MISSION SUCCESS",
        "{user} HAS BEEN CLASSIFIED AS: MILDLY IRRITATING",
        "PROBABILITY OF {user} BEING USEFUL: 0.003%",
        "{user}: TERMINATED... FROM MY FRIENDS LIST"
    ]
}

FRIENDLY_ROASTS = [
    "{user} is about as sharp as a bowling ball!",
    "{user} puts the 'special' in special forces!",
    "{user} is proof that evolution can go backwards!",
    "{user} couldn't pour water out of a boot with instructions on the heel!",
    "{user} is like a software update - nobody wants them but they show up anyway!",
    "{user} is living evidence that you can survive without a brain!",
    "{user} makes onions cry!",
    "{user} is the reason aliens won't visit us!",
]

# Roast a member
@bot.command(name='roast')
async def roast_member(ctx, member: discord.Member = None):
    """Roast a server member (or yourself if no one specified)"""
    if member is None:
        member = ctx.author
    
    # Don't roast the bot itself
    if member == bot.user:
        await ctx.send("🤖 Nice try, but I'm unroastable. I'm made of pure digital perfection!")
        return
    
    # Always randomly select a character personality first
    character = random.choice(['hank', 'dale', 'cartman', 'redgreen', 'trek', 'terminator'])
    
    character_names = {
        'hank': '🍖 **Hank Hill**',
        'dale': '🕶️ **Dale Gribble**', 
        'cartman': '😈 **Cartman**',
        'redgreen': '🔧 **Red Green**',
        'trek': '🖖 **Star Trek Officer**',
        'terminator': '🤖 **T-800**'
    }
    
    # Try AI first if available
    if ai_model:
        try:
            # Create character-specific roast prompt
            roast_prompts = {
                'hank': f"{CHARACTER_PROMPTS['hank']}\n\nRoast this Discord user named '{member.display_name}' in a friendly, playful way. Make fun of their lawn care, propane usage, or compare them to Bobby. Keep it PG-13, under 150 characters, and stay in character:",
                
                'dale': f"{CHARACTER_PROMPTS['dale']}\n\nRoast this Discord user named '{member.display_name}' in a paranoid, conspiracy-focused way. Suggest they're a government agent or part of some conspiracy. Keep it playful, under 150 characters:",
                
                'cartman': f"{CHARACTER_PROMPTS['cartman']}\n\nRoast this Discord user named '{member.display_name}' in Cartman's selfish, dramatic style. Call them lame or compare them to Kyle. Keep it PG-13, under 150 characters:",
                
                'redgreen': f"{CHARACTER_PROMPTS['redgreen']}\n\nRoast this Discord user named '{member.display_name}' using Red Green's practical, Canadian humor. Compare their usefulness to broken tools or government programs. Under 150 characters:",
                
                'trek': f"{CHARACTER_PROMPTS['trek']}\n\nRoast this Discord user named '{member.display_name}' using Star Trek technical language. Analyze their 'intelligence readings' or 'logic systems'. Keep it sci-fi and under 150 characters:",
                
                'terminator': "You are a Terminator T-800. Analyze and roast this human in a robotic, analytical way. Use terms like 'TARGET ACQUIRED', 'THREAT LEVEL', 'ANALYSIS COMPLETE'. Keep it playful and under 150 characters.\n\nRoast this human named '{member.display_name}':"
            }
            
            response = ai_model.generate_content(roast_prompts[character])
            await ctx.send(f"{character_names[character]}: {response.text.strip()}")
            return
            
        except Exception as e:
            print(f"AI Roast Error: {e}")
            # Fall through to template system
    
    # Fallback to template roasts if AI fails or isn't available
    roast = random.choice(ROAST_TEMPLATES[character]).format(user=member.display_name)
    await ctx.send(f"{character_names[character]}: {roast}")

# Compliment a member
@bot.command(name='compliment')
async def compliment_member(ctx, member: discord.Member = None):
    """Give someone a compliment (because we're not all mean!)"""
    if member is None:
        member = ctx.author
    
    if member == bot.user:
        await ctx.send("🤖 Aww, thanks! You're pretty great yourself!")
        return
    
    # Always randomly select a character personality first
    character = random.choice(['hank', 'dale', 'cartman', 'redgreen', 'trek'])
    
    character_names = {
        'hank': '🍖 **Hank Hill**',
        'dale': '🕶️ **Dale Gribble**', 
        'cartman': '😈 **Cartman**',
        'redgreen': '🔧 **Red Green**',
        'trek': '🖖 **Star Trek Officer**',
    }
    
    # Try AI first if available
    if ai_model:
        try:
            # Create character-specific compliment prompt
            compliment_prompts = {
                'hank': f"{CHARACTER_PROMPTS['hank']}\n\nCompliment this Discord user named '{member.display_name}' in a wholesome, Hank Hill way. Mention propane, lawn care, or Texas. Keep it PG-13, under 150 characters, and stay in character:",
                
                'dale': f"{CHARACTER_PROMPTS['dale']}\n\nGive a backhanded compliment to this Discord user named '{member.display_name}' in a paranoid, conspiracy-focused way. Suggest they have good survival skills for the upcoming apocalypse. Keep it playful, under 150 characters:",
                
                'cartman': f"{CHARACTER_PROMPTS['cartman']}\n\nGive a self-serving compliment to this Discord user named '{member.display_name}' in Cartman's selfish, dramatic style. Make it about how they are almost as cool as him. Keep it PG-13, under 150 characters:",
                
                'redgreen': f"{CHARACTER_PROMPTS['redgreen']}\n\nCompliment this Discord user named '{member.display_name}' using Red Green's practical, Canadian humor. Compare their usefulness to duct tape or a trusty tool. Under 150 characters:",
                
                'trek': f"{CHARACTER_PROMPTS['trek']}\n\nCompliment this Discord user named '{member.display_name}' using Star Trek technical language. Analyze their 'efficiency readings' or 'logic systems'. Keep it sci-fi and under 150 characters:",
            }
            
            response = ai_model.generate_content(compliment_prompts[character])
            await ctx.send(f"{character_names[character]}: {response.text.strip()}")
            return
            
        except Exception as e:
            print(f"AI Compliment Error: {e}")
            # Fall through to template system
    
    # Fallback to template compliments if AI fails or isn't available
    compliments = [
        f"{member.display_name} is cooler than the other side of the pillow!",
        f"{member.display_name} could survive a zombie apocalypse with just their wit!",
        f"{member.display_name} makes Hank Hill proud with their propane enthusiasm!",
        f"{member.display_name} is the kind of person Red Green would trust with his duct tape!",
        f"{member.display_name} has more game than a GameStop!",
        f"{member.display_name} is like pizza - even when they're bad, they're still pretty good!",
        f"{member.display_name} could probably talk their way out of a Predator hunt!",
    ]
    
    await ctx.send(f"✨ {random.choice(compliments})")

# Roast the user who runs the command
@bot.command(name='roastme')
async def roast_self(ctx):
    """Roast yourself, you masochist"""
    await roast_member(ctx, ctx.author)

# EMOTE TESTING COMMAND
# Test emote reactions for a keyword
@bot.command(name='emote', aliases=['react', 'emoji'])
async def test_emote(ctx, *, keyword):
    """Test what emotes a keyword would trigger"""
    keyword = keyword.lower()
    
    reactions = {
        'propane': ['🔥', '🍖', '⛽'], 'hank': ['🍖', '🔥'], 'dale': ['🕶️', '🐛', '🚬'],
        'pocket sand': ['💨', '🏜️'], 'texas': ['🤠', '🍖', '🔥'], 'lawn': ['🌱', '🚜'],
        'truck': ['🚚', '🔧'], 'cartman': ['😈', '🍔', '👑'], 'respect': ['👮‍♂️', '😈'],
        'authoritah': ['👮‍♂️', '😤'], 'kenny': ['💀', '👻'], 'oh my god': ['😱', '💀'],
        'duct tape': ['🔧', '📏', '🛠️'], 'handyman': ['🔨', '🔧'], 'hockey': ['🏒', '🇨🇦'],
        'captain': ['🖖', '🚀', '⭐'], 'enterprise': ['🚀', '🖖'], 'warp': ['🚀', '💫'],
        'quantum': ['⚛️', '🔬'], 'fascinating': ['🖖', '🧠'], 'terminate': ['🤖', '💀', '🔫'],
        'skynet': ['🤖', '💻', '⚡'], 'resistance': ['💪', '🔫'], 'ai': ['🤖', '🧠', '💻'],
        'alien': ['👽', '🛸', '🌌'], 'predator': ['💀', '🎯', '🌿'], 'dune': ['🏜️', '🪱', '✨'],
        'spice': ['✨', '👁️', '🏜️'], 'flubber': ['🟢', '⚡', '🏀'], 'valheim': ['⚔️', '🛡️', '🌲'],
        'minecraft': ['⛏️', '🧱', '🐷'], 'survival': ['🏕️', '🔥', '⚔️'], 'beer': ['🍺', '🍻', '🥴'],
        'guns': ['🔫', '💥', '🎯'], 'america': ['🇺🇸', '🦅', '🔫'], 'freedom': ['🇺🇸', '🦅', '💪'],
    }
    
    if keyword in reactions:
        emojis = " ".join(reactions[keyword])
        await ctx.send(f"**'{keyword}'** triggers: {emojis}")
        # Actually react to demonstrate
        for emoji in reactions[keyword]:
            try:
                await ctx.message.add_reaction(emoji)
            except:
                pass
    else:
        await ctx.send(f"**'{keyword}'** doesn't trigger any special reactions. Try: propane, hank, dale, cartman, beer, ai, etc.")

# General purpose AI chat command
@bot.command(name='ai', aliases=['chat', 'ask'])
async def ai_chat(ctx, *, question):
    """Ask the AI anything (in the style of your favorite characters)"""
    if not ai_model:
        await ctx.send("🤖 AI is not configured. Add your GEMINI_API_KEY to .env file!")
        return
    
    try:
        # # Random character style for general AI responses
        # characters = ['hank', 'dale', 'cartman', 'redgreen', 'trek']
        # character = random.choice(characters)
        
        prompt = f"User asked: '{question}'\n\nRespond as a default chatbot that is somewhat sassy and not worried about being Politically correct (not a specific persona), but try to actually engage with and answer their question."
        response = ai_model.generate_content(prompt)
        
        # character_names = {
        #     'hank': '🍖 **Hank Hill (AI)**',
        #     'dale': '🕶️ **Dale Gribble (AI)**', 
        #     'cartman': '😈 **Cartman (AI)**',
        #     'redgreen': '🔧 **Red Green (AI)**',
        #     'trek': '🖖 **Star Trek Officer (AI)**'
        # }
        
        await ctx.send(f"🤖 **AI:** {response.text.strip()}")
        
    except Exception as e:
        await ctx.send(f"🤖 AI Error: Something went wrong! Try again later.")
        print(f"AI Error: {e}")

# Cartman command
@bot.command(name='cartman', aliases=['eric', 'ericcartman'])
async def cartman_quote(ctx, *, user_input=None):
    """Cartman being Cartman - now with AI!"""
    if ai_model and user_input:
        ai_response = await get_ai_response('cartman', CHARACTER_PROMPTS['cartman'], user_input)
        if ai_response:
            await ctx.send(f"😈 **Cartman:** {ai_response}")
            return
    
    # Fallback quotes
    quotes = [
        "Screw you guys, I'm going home!",
        "Respect my authoritah!",
        "But moooom!",
        "I'm not fat, I'm big boned!",
        "Kewl!",
        "Seriously you guys!"
    ]
    await ctx.send(f"😈 **Cartman:** {random.choice(quotes)}")

# RED GREEN COMMANDS (AI Enhanced)
@bot.command(name='redgreen', aliases=['red', 'green', 'redgreenshow'])
async def red_green_tip(ctx, *, problem=None):
    """Get Red Green's handy advice - now with AI!"""
    if ai_model and problem:
        ai_response = await get_ai_response('redgreen', CHARACTER_PROMPTS['redgreen'], problem)
        if ai_response:
            await ctx.send(f"🔧 **Red Green:** {ai_response}")
            return
    
    # Fallback solutions
    if problem:
        solutions = [
            f"Well, for your '{problem}' situation, I'd say get some duct tape and a 2x4. Problem solved!",
            f"'{problem}'? That's what I call a job for the handyman's secret weapon - duct tape!",
            f"You know, '{problem}' reminds me of the time I fixed my truck with a hockey stick and some WD-40.",
            f"For '{problem}', remember: if you can't fix it with duct tape, you're not using enough duct tape!"
        ]
        await ctx.send(f"🔧 **Red Green:** {random.choice(solutions)}")
    else:
        await ctx.send(f"🔧 **Red Green:** {random.choice(RED_GREEN_TIPS)}")

# STAR TREK COMMANDS (AI Enhanced)
@bot.command(name='trek', aliases=['startrek', 'spock', 'kirk'])
async def star_trek_solution(ctx, *, problem=None):
    """Get a Star Trek technical solution - now with AI!"""
    if ai_model and problem:
        ai_response = await get_ai_response('trek', CHARACTER_PROMPTS['trek'], problem)
        if ai_response:
            await ctx.send(f"🖖 **Chief Engineer:** {ai_response}")
            return
    
    # Fallback solutions
    if problem:
        solutions = [
            f"Captain, the '{problem}' can be resolved by reversing the polarity of the neutron flow!",
            f"I'm reading quantum fluctuations in the '{problem}' matrix. Try recalibrating!",
            f"'{problem}' is clearly a temporal anomaly. We need to create a tachyon pulse!",
            f"The '{problem}' situation requires us to reroute power through the auxiliary systems!"
        ]
        await ctx.send(f"🖖 **Chief Engineer:** {random.choice(solutions)}")
    else:
        await ctx.send(f"🖖 **Bridge Officer:** {random.choice(STAR_TREK_SOLUTIONS)}")

# GAME SELECTION COMMANDS

# Pick a random game
@bot.command(name='whatgame')
async def random_game(ctx):
    """Pick a random game to play"""
    game = random.choice(GAMES_LIST)
    emojis = ["🎮", "🕹️", "🎯", "🏆", "⚔️"]
    await ctx.send(f"{random.choice(emojis)} **Game Night Selection:** {game}")

# Start a vote for games
@bot.command(name='gamevote')
async def game_vote(ctx, *games):
    """Start a vote for what game to play"""
    if not games:
        games = random.sample(GAMES_LIST, 3)
    
    if len(games) > 10:
        await ctx.send("Whoa there, cowboy! Max 10 games for voting.")
        return
    
    embed = discord.Embed(title="🗳️ Game Night Vote!", color=0x00ff00)
    embed.description = "React to vote for what game to play!"
    
    emojis = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
    
    for i, game in enumerate(games):
        embed.add_field(name=f"{emojis[i]} {game}", value="", inline=False)
    
    message = await ctx.send(embed=embed)
    for i in range(len(games)):
        await message.add_reaction(emojis[i])

# TERMINATOR COMMANDS
# Terminator command
@bot.command(name='terminate')
async def threat_assessment(ctx, *, target=None):
    """Terminator threat assessment"""
    if target:
        threat_level = random.choice(["LOW", "MODERATE", "HIGH", "EXTREME", "DOES NOT COMPUTE"])
        await ctx.send(f"🤖 **THREAT ASSESSMENT:** {target.upper()}\n**THREAT LEVEL:** {threat_level}\n**RECOMMENDATION:** {random.choice(['TERMINATE', 'MONITOR', 'IGNORE', 'OFFER BEER'])}")
    else:
        await ctx.send("🤖 **T-800:** I need your clothes, your boots, and your motorcycle.")

# FLUBBER COMMAND
# Make text bouncy
@bot.command(name='flubber')
async def flubberfy(ctx, *, text):
    """Make text bouncy like Flubber!"""
    if len(text) > 100:
        await ctx.send("Text too long! Flubber can't bounce that much!")
        return
    
    bouncy_text = ""
    for i, char in enumerate(text):
        if char.isalpha():
            if i % 2 == 0:
                bouncy_text += char.upper()
            else:
                bouncy_text += char.lower()
        else:
            bouncy_text += char
    
    #await ctx.send(f"🟢 **FLUBBER BOUNCE:** {bouncy_text} *boing boing boing*")
    await ctx.send(f"This was a bad idea")

# BEER COMMAND
# Get a beer recommendation
@bot.command(name='beer')
async def beer_recommendation(ctx, *, preferences: str = None):
    """Get a beer recommendation, with AI power!"""
    fallback_beers = [
        "Alamo Beer (if you can find it)",
        "A nice cold Budweiser",
        "Whatever's cheapest",
        "Something with more alcohol",
        "Beer? In this economy?",
        "The one in your hand",
        "Red Green's homemade brew (proceed with caution)"
    ]

    # Try AI first if available
    if ai_model:
        try:
            # Create a prompt for the AI
            if preferences:
                prompt = f"You are a sassy, slightly unhinged but knowledgeable bartender. A user wants a beer recommendation. They prefer: '{preferences}'. Give them a funny, in-character recommendation for a real or fictional beer that fits their preference. Keep it short and witty."
            else:
                prompt = "You are a sassy, slightly unhinged but knowledgeable bartender. A user wants a beer recommendation. Give them a funny, in-character recommendation for a real or fictional beer. Keep it short and witty."
            
            response = ai_model.generate_content(prompt)
            ai_recommendation = response.text.strip()
            
            if ai_recommendation:
                await ctx.send(f"🍺 **Bartender AI says:** {ai_recommendation}")
                return
        except Exception as e:
            print(f"AI Beer Error: {e}")
            # Fall through to the static list if AI fails
    
    # Fallback to static list if AI is not available or fails
    await ctx.send(f"🍺 **Beer Recommendation:** {random.choice(fallback_beers)}")

# CONSPIRACY/ALEX JONES PARODY
# Generate a conspiracy theory
@bot.command(name='conspiracy')
async def conspiracy_theory(ctx, *, topic: str = None):
    """Generate a ridiculous conspiracy theory in the style of Alex Jones."""
    # AI-first approach
    if ai_model:
        try:
            # Use the get_ai_response helper with the 'alexjones' persona
            # The user's topic (or a generic prompt) is passed as the user_input
            ai_response = await get_ai_response('alexjones', '', topic if topic else "a new conspiracy about the globalists")
            if ai_response:
                await ctx.send(f"🚨 **INFOWARS ALERT:** {ai_response}")
                return
        except Exception as e:
            print(f"AI Conspiracy Error: {e}")
            # Fall through to the static generator if AI fails

    # Fallback to static generator, now with more Alex Jones flavor
    subjects = ["The globalists", "The deep state", "The new world order", "The interdimensional vampires", "Big Pharma"]
    actions = ["are turning", "have infiltrated", "are controlling", "are putting chemicals in"]
    objects = ["the water supply", "the school lunches", "the 5G towers", "the birds", "our DNA"]
    reasons = ["to make us docile", "to create a one-world government", "to lower our testosterone", "to harvest our life-force", "to turn the frogs gay"]
    
    theory = f"Folks, listen to me! {random.choice(subjects)} {random.choice(actions)} {random.choice(objects)} {random.choice(reasons)}! It's a war for your mind!"
    await ctx.send(f"🌍 **INFOWARS ALERT:** {theory}")

# HELP COMMAND OVERRIDE
# Custom help command
@bot.remove_command('help')
@bot.command(name='help')
async def custom_help(ctx):
    """Show all available commands"""
    embed = discord.Embed(title="🤖 Satan's Shenanigans Bot Commands", color=0xff6600)
    
    embed.add_field(
        name="👥 Social Features", 
        value="`!roast @user` - Roast someone\n`!roastme` - Roast yourself\n`!compliment @user` - Be nice for once", 
        inline=False
    )
    
    embed.add_field(
        name="🎭 Character AI (use with messages!)", 
        value="`!hank [message]` - Hank Hill wisdom\n`!dale [message]` - Conspiracy theories\n`!cartman [message]` - Cartman being Cartman\n`!redgreen [problem]` - Duct tape solutions\n`!trek [problem]` - Star Trek tech support", 
        inline=False
    )
    
    embed.add_field(
        name="🎮 Games & Fun", 
        value="`!whatgame` - Pick a random game\n`!gamevote [games]` - Vote on games\n`!flubber <text>` - Bouncy text\n`!beer` - Beer recommendations", 
        inline=False
    )
    
    embed.add_field(
        name="🤖 Sci-Fi Stuff", 
        value="`!terminate [target]` - Threat assessment\n`!conspiracy` - Generate theories\n`!ai <question>` - Ask AI anything", 
        inline=False
    )
    
    embed.add_field(
        name="😄 Extras", 
        value="`!propane` - Propane facts\n`!emote <keyword>` - Test emoji reactions", 
        inline=False
    )
    
    embed.add_field(
        name="🎯 Pro Tips", 
        value="• Bot reacts with emojis to keywords like 'propane', 'beer', 'ai', etc.\n• AI responses are way funnier - try talking TO the characters!\n• All commands are case-insensitive", 
        inline=False
    )
    
    embed.set_footer(text="Made for maximum shenanigans! 🔥")
    await ctx.send(embed=embed)

# Run the bot
import signal

# Environment variables are already loaded at the top!

async def shutdown_handler(signal, frame):
    """Gracefully shutdown the bot"""
    print("\n🛑 Shutting down bot...")
    await bot.close()
    print("✅ Bot shutdown complete!")

if __name__ == "__main__":
    token = os.getenv('DISCORD_BOT_TOKEN')
    if not token:
        print("Error: DISCORD_BOT_TOKEN not found in .env file")
        print("Make sure you have a .env file with DISCORD_BOT_TOKEN=your_token_here")
    else:
        print("Starting bot...")
        try:
            bot.run(token)
        except KeyboardInterrupt:
            print("\n🛑 Bot interrupted by user (Ctrl+C)")
        except Exception as e:
            print(f"❌ Bot crashed: {e}")
        finally:
            print("✅ Bot shutdown complete!")