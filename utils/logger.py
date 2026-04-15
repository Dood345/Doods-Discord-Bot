import logging
import logging.handlers
import os

def setup_logging(log_file="data/logs/bot.log"):
    """
    Cave Johnson Logistics & Diagnostics Logging Initialization
    Configures a highly-structured text logging format with file rotation.
    """
    
    # Ensure log directory exists
    os.makedirs(os.path.dirname(log_file), exist_ok=True)
    
    # Get the root logger
    logger = logging.getLogger()
    logger.setLevel(logging.INFO) # Set base level for the entire app
    
    # If the logger already has handlers, remove them to avoid duplicate logs
    if logger.hasHandlers():
        logger.handlers.clear()
        
    # Standard Aperture Science Highly-Structured Formatting
    # Format: [YYYY-MM-DD HH:MM:SS] [LEVEL] [MODULE:FUNC] - Message
    formatter = logging.Formatter(
        fmt='[%(asctime)s] [%(levelname)-8s] [%(name)s:%(funcName)s] - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # 1. Console Output Setup
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # 2. File Output Setup (Rotating File Handler)
    # 5 megabytes (5 * 1024 * 1024 bytes) max per file, keep 5 backups
    file_handler = logging.handlers.RotatingFileHandler(
        filename=log_file,
        encoding='utf-8',
        maxBytes=5 * 1024 * 1024,
        backupCount=5
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    # --- Aperture Science Noise Cancellation ---
    # Discord.py internal logging is highly verbose. We clamp them to WARNING level.
    logging.getLogger('discord').setLevel(logging.WARNING)
    logging.getLogger('discord.http').setLevel(logging.WARNING)
    logging.getLogger('discord.gateway').setLevel(logging.WARNING)
    
    # You can also silence Pycord/Discord audio logging if that gets noisy
    logging.getLogger('discord.voice_state').setLevel(logging.WARNING)

    logger.info("Aperture Science highly-structured diagnostic logging initialized.")
