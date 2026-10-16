"""Configuration and data for the Discord bot"""
import os
import json
import logging

from utils.personas import load_personas

logger = logging.getLogger(__name__)


def _load_server_contexts(path: str) -> dict:
    """Load per-guild AI flavor text from a private (gitignored) JSON file.

    JSON keys are strings; guild IDs from discord.py are ints, so keys are converted.
    A missing or malformed file falls back to {} (every guild gets the default context).
    """
    try:
        with open(path, 'r', encoding='utf-8') as f:
            raw = json.load(f)
        return {int(k): v for k, v in raw.items() if not k.startswith('_')}
    except FileNotFoundError:
        logger.info(f"No server contexts file at {path}; using default context for all guilds")
    except (ValueError, AttributeError) as e:
        logger.error(f"Invalid server contexts file {path}: {e}")
    return {}

class BotConfig:
    # Character personas live in content/personas.json (see utils/personas.py)
    PERSONAS = load_personas()
    CHARACTER_PROMPTS = {key: p.prompt for key, p in PERSONAS.items()}
    CHARACTER_INFO = {key: {'name': p.label, 'emoji': p.emoji} for key, p in PERSONAS.items()}

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

    # AI Configuration
    OLLAMA_URL = os.getenv('OLLAMA_URL')  # e.g. http://localhost:11434
    OLLAMA_MODEL = os.getenv('OLLAMA_MODEL', 'gemma4:12b')
    # Embedding model for recalling old chats (e.g. nomic-embed-text); unset disables recall
    OLLAMA_EMBED_MODEL = os.getenv('OLLAMA_EMBED_MODEL')

    # Music Configuration
    MUSIC_DEFAULT_VOLUME = float(os.getenv('MUSIC_DEFAULT_VOLUME', '0.5'))
    MUSIC_TTS_VOICE = os.getenv('MUSIC_TTS_VOICE', 'en-US-ChristopherNeural')
    MUSIC_BITRATE = int(os.getenv('MUSIC_BITRATE', '128'))  # kbps Opus sent to Discord
    # bgutil PO-token provider (Docker container) that helps yt-dlp pass YouTube's bot checks
    YT_POT_PROVIDER_URL = os.getenv('YT_POT_PROVIDER_URL', 'http://127.0.0.1:4416')
    # Plex music library, searched before SoundCloud/YouTube for song requests
    PLEX_URL = os.getenv('PLEX_URL') or (f"http://{os.getenv('PLEX_IP')}:32400" if os.getenv('PLEX_IP') else None)
    PLEX_TOKEN = os.getenv('PLEX_TOKEN')

    # Doodlab Configuration
    # Printer Host (IP:Port for Moonraker/Fluidd)
    # Printer Host (IP:Port for Moonraker/Fluidd)
    PRINTER_HOST = os.getenv('PRINTER_HOST')
    # Default webcam snapshot URL (Standard Moonraker/MJPEG-Streamer)
    PRINTER_WEBCAM_URL = f"http://{PRINTER_HOST}/webcam/?action=snapshot" if PRINTER_HOST else None
    
    # Server IDs (Comma separated in .env)
    # SERVER_ID=123,456
    _server_ids_str = os.getenv('SERVER_ID', '')
    SERVER_IDS = [int(id.strip()) for id in _server_ids_str.split(',') if id.strip().isdigit()]

    # Authorization
    # Restricted commands (homelab/printer) only for these users
    OWNER_ID = int(os.getenv('OWNER_ID', 0))
    _allowed_users_str = os.getenv('ALLOWED_USERS', 'dood345') # Defaults to dood345
    ALLOWED_USERS = [u.strip().lower() for u in _allowed_users_str.split(',')]

    # Internal Services to Ping for /doodlab
    # These now pull from .env
    HOMELAB_SERVICES = [
        {"name": "Qidi Printer", "ip": os.getenv('PRINTER_IP')},
        {"name": "Router", "ip": os.getenv('ROUTER_IP')},
        {"name": "Pi-hole", "ip": os.getenv('PIHOLE_IP')},
        {"name": "Doodlab", "ip": os.getenv('DOODLAB_IP')},
        {"name": "Plex", "ip": os.getenv('PLEX_IP')}
    ]

    # --- HOMELAB API CONFIGURATION ---
    # Overseerr (The Request Manager)
    OVERSEERR_URL = os.getenv('OVERSEERR_URL')
    OVERSEERR_API_KEY = os.getenv('OVERSEERR_API_KEY')

    # Sonarr (TV Shows)
    SONARR_URL = os.getenv('SONARR_URL')
    SONARR_API_KEY = os.getenv('SONARR_API_KEY')

    # Radarr (Movies)
    RADARR_URL = os.getenv('RADARR_URL')
    RADARR_API_KEY = os.getenv('RADARR_API_KEY')

    # Lidarr (Music)
    LIDARR_URL = os.getenv('LIDARR_URL')
    LIDARR_API_KEY = os.getenv('LIDARR_API_KEY')


    # ComfyUI Configuration
    COMFY_URL = os.getenv('COMFY_URL')

    # --- SERVER CONTEXT MAPPING ---
    # Per-guild AI flavor text, keyed by guild ID. Kept out of git because it holds
    # real server IDs and names. See data/server_contexts.example.json for the format.
    SERVER_CONTEXTS_FILE = os.getenv('SERVER_CONTEXTS_FILE', 'data/server_contexts.json')
    SERVER_CONTEXTS = _load_server_contexts(SERVER_CONTEXTS_FILE)
