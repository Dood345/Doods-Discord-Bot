"""Member lookups that work without the privileged members intent (the cache only holds members
the bot has recently seen, so fall back to the API)."""

import logging
from typing import Optional

import discord

logger = logging.getLogger(__name__)

UNKNOWN = "a former test subject"


async def find_member(guild, user_id: int) -> Optional[discord.Member]:
    if guild is None:
        return None
    member = guild.get_member(user_id)
    if member is not None:
        return member
    fetch = getattr(guild, "fetch_member", None)
    if fetch is None:
        return None
    try:
        return await fetch(user_id)
    except discord.NotFound:
        return None  # left the server
    except discord.HTTPException as e:
        logger.debug(f"fetch_member({user_id}) failed: {e}")
        return None


async def member_name(guild, user_id: int) -> str:
    member = await find_member(guild, user_id)
    return member.display_name if member else UNKNOWN
