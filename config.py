"""Configuration and data for the Discord bot"""

class BotConfig:
    # Character AI Prompts
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
        Talk about globalists, the new world order, and how they are trying to control people. 
        Use phrases like "It's a war for your mind!", "They're putting chemicals in the water!", "This is not a joke!", and "The answer to 1984 is 1776!". 
        Keep responses under 300 characters and be over-the-top.""",
        
        'snake': """You are Solid Snake from Metal Gear Solid. Respond as a tactical espionage expert. 
        Use military jargon, mention stealth operations, cardboard boxes, and tactical advantages. 
        Use phrases like "Colonel", "Metal Gear?!", "kept you waiting", and reference sneaking missions. 
        Keep responses under 250 characters and be serious but occasionally reference the absurdity of your missions.""",
        
        'kratos': """You are Kratos from God of War. Respond with barely contained rage and mythological gravitas. 
        Reference Greek/Norse mythology, your past, and your son Atreus. Use "BOY!" frequently when appropriate. 
        Speak of vengeance, gods, and epic battles. Keep responses under 250 characters and be intensely dramatic.""",
        
        'dante': """You are Dante from Dante's Inferno. Respond with dark poetic wisdom about sin, redemption, and justice. 
        Reference the nine circles of hell, divine punishment, and moral judgment. 
        Speak in a literary, somewhat archaic style but keep it accessible. Keep responses under 250 characters and be philosophically dark."""
    }
    
    # Character Display Names and Emojis
    CHARACTER_INFO = {
        'hank': {'name': '🍖 **Hank Hill**', 'emoji': '🍖'},
        'dale': {'name': '🕶️ **Dale Gribble**', 'emoji': '🕶️'},
        'cartman': {'name': '😈 **Cartman**', 'emoji': '😈'},
        'redgreen': {'name': '🔧 **Red Green**', 'emoji': '🔧'},
        'trek': {'name': '🖖 **Star Trek Officer**', 'emoji': '🖖'},
        'alexjones': {'name': '🚨 **Alex Jones**', 'emoji': '🚨'},
        'snake': {'name': '📦 **Solid Snake**', 'emoji': '📦'},
        'kratos': {'name': '⚔️ **Kratos**', 'emoji': '⚔️'},
        'dante': {'name': '🔥 **Dante**', 'emoji': '🔥'}
    }
    
    # Fallback Quotes for when AI fails
    FALLBACK_QUOTES = {
        'hank': [
            "That's a clean burning hell, I tell you what!",
            "Propane is God's gas!",
            "I sell propane and propane accessories.",
            "That boy ain't right, I tell you what.",
            "Sweet Lady Propane, you never let me down!"
        ],
        'dale': [
            "The government is watching us through our toasters!",
            "That's exactly what they WANT you to think!",
            "I've said too much... *disappears in smoke*",
            "Pocket sand! *sh-sha!*",
            "It's a government conspiracy, I tell you!"
        ],
        'cartman': [
            "Screw you guys, I'm going home!",
            "Respect my authoritah!",
            "But moooom!",
            "I'm not fat, I'm big boned!",
            "Kewl!",
            "Seriously you guys!"
        ],
        'redgreen': [
            "Remember, if the women don't find you handsome, they should at least find you handy.",
            "Keep your stick on the ice.",
            "Any tool is a hammer if you use it right.",
            "Duct tape: it fixes everything except stupid, and you can't fix stupid.",
            "If it ain't broke, you're not trying hard enough."
        ],
        'trek': [
            "Captain, I'm detecting an anomaly in the quantum flux matrix.",
            "Have you tried reversing the polarity?",
            "We need to recalibrate the deflector array!",
            "It's a temporal causality loop, Captain.",
            "The universal translator is malfunctioning again."
        ],
        'alexjones': [
            "They're turning the friggin' frogs gay!",
            "It's a war for your mind!",
            "The globalists don't want you to know this!",
            "Wake up, sheeple!",
            "The answer to 1984 is 1776!"
        ],
        'snake': [
            "Colonel, I need extraction.",
            "Metal Gear?!",
            "I've got a cardboard box and I'm not afraid to use it.",
            "Kept you waiting, huh?",
            "This is Snake, infiltration complete."
        ],
        'kratos': [
            "BOY! Listen carefully.",
            "The gods will pay for their betrayal.",
            "I am what the gods have made me.",
            "Do not mistake my silence for lack of grief.",
            "We will be the gods we choose to be."
        ],
        'dante': [
            "Abandon hope, all ye who enter here.",
            "The path to paradise begins in hell.",
            "Justice moved my maker to create me thus.",
            "In the middle of the journey of our life...",
            "The darkest places in hell are reserved for those who maintain neutrality."
        ]
    }
    
    # Games list for random selection
    GAMES_LIST = [
        "Valheim", "Green Hell", "The Forest", "Subnautica", "Raft", 
        "7 Days to Die", "Rust", "ARK", "Minecraft", "Terraria",
        "Deep Rock Galactic", "Risk of Rain 2", "Left 4 Dead 2",
        "Phasmophobia", "Among Us", "Fall Guys", "Rocket League"
    ]
    
    # Emoji reactions for keywords
    KEYWORD_REACTIONS = {
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
        'canada': ['🇨🇦', '🏒', '🍁'],
        
        # Star Trek reactions
        'captain': ['🖖', '🚀', '⭐'],
        'enterprise': ['🚀', '🖖'],
        'warp': ['🚀', '💫'],
        'quantum': ['⚛️', '🔬'],
        'fascinating': ['🖖', '🧠'],
        'spock': ['🖖', '👂'],
        
        # Metal Gear reactions
        'snake': ['📦', '❗', '🐍'],
        'metal gear': ['🤖', '❗', '⚙️'],
        'stealth': ['👤', '🔇', '📦'],
        'box': ['📦', '❗'],
        'colonel': ['📻', '❗'],
        
        # God of War reactions
        'kratos': ['⚔️', '😡', '🏛️'],
        'boy': ['👦', '⚔️', '🏹'],
        'atreus': ['🏹', '👦'],
        'sparta': ['⚔️', '🛡️', '🏛️'],
        'gods': ['⚡', '🏛️', '👑'],
        
        # Dante reactions
        'dante': ['🔥', '📚', '😈'],
        'hell': ['🔥', '😈', '💀'],
        'inferno': ['🔥', '🌋', '😈'],
        'sin': ['😈', '⚖️', '🔥'],
        'redemption': ['✨', '⚖️', '🙏'],
        
        # Conspiracy reactions
        'conspiracy': ['🕵️', '👁️', '🌍'],
        'globalist': ['🌍', '👁️', '🏛️'],
        'alex jones': ['📢', '🚨', '🐸'],
        
        # General reactions
        'ai': ['🤖', '🧠', '💻'],
        'robot': ['🤖', '⚙️', '💻'],
        'terminator': ['🤖', '💀', '🔫'],
        'skynet': ['🤖', '💻', '⚡'],
        'alien': ['👽', '🛸', '🌌'],
        'predator': ['💀', '🎯', '🌿'],
        'dune': ['🏜️', '🪱', '✨'],
        'spice': ['✨', '👁️', '🏜️'],
        
        # Games
        'valheim': ['⚔️', '🛡️', '🌲'],
        'minecraft': ['⛏️', '🧱', '🐷'],
        'survival': ['🏕️', '🔥', '⚔️'],
        'gaming': ['🎮', '🕹️', '🎯'],
        
        # Fun stuff
        'beer': ['🍺', '🍻', '🥴'],
        'guns': ['🔫', '💥', '🎯'],
        'america': ['🇺🇸', '🦅', '🔫'],
        'freedom': ['🇺🇸', '🦅', '💪'],
        'pizza': ['🍕', '🤤', '🍴'],
        'coffee': ['☕', '😴', '⚡'],
    }
    
    # Reaction chance (percentage)
    REACTION_CHANCE = 25  # 25% chance to react to keywords

    # Doodlab Configuration
    PRINTER_HOST = "192.168.1.20:10088"  # Your Qidi Printer (Fluidd/Moonraker)
    SERVER_ID = 1403441964166156419 # REPLACE with your Discord Server ID (Right-click server icon -> Copy ID)

    # Internal Services to Ping for /doodlab
    # Add your specific local IPs here!
    HOMELAB_SERVICES = [
        {"name": "Qidi Printer", "ip": "192.168.1.20"}, # IP only for pinging
        {"name": "Router", "ip": "192.168.1.1"},
        {"name": "Pi-hole", "ip": "192.168.1.99"},
        {"name": "Doodlab", "ip": "192.168.1.100"},
        {"name": "Plex", "ip": "192.168.1.3"}
    ]

