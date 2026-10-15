"""Authorization helpers shared by slash commands and AI tools"""

from config import BotConfig


def is_authorized(user) -> bool:
    """True if this Discord user may use restricted (homelab) features.

    Always pass the human who triggered the action (interaction.user / message.author),
    never anything the AI model claims.
    """
    if user is None:
        return False
    if BotConfig.OWNER_ID and user.id == BotConfig.OWNER_ID:
        return True
    return user.name.lower() in BotConfig.ALLOWED_USERS
