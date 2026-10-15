"""Tools Cave Johnson can call from chat. Each wraps an existing service; no business logic here.

Tool output is read back to the user in a (possibly public) channel: never include IPs, hostnames or keys.
"""

from utils.agent import Tool, ToolContext, ToolRegistry


async def _recommend_games(ctx: ToolContext, players: int = 0, tag: str = None) -> str:
    try:
        players = int(players or 0)
    except (TypeError, ValueError):
        players = 0
    return await ctx.bot.db.recommend_games(guild_id=ctx.guild.id, min_players=players, tag=tag or None)


async def _list_game_tags(ctx: ToolContext) -> str:
    tags = await ctx.bot.db.get_tags(ctx.guild.id)
    return "Game tags in this server's library: " + (", ".join(tags) if tags else "none yet")


async def _now_playing(ctx: ToolContext) -> str:
    music = ctx.bot.get_cog("MusicCommands")
    if music is None:
        return "The music system is offline."
    return music.get_music_status(ctx.guild)


async def _service_status(ctx: ToolContext) -> str:
    services = await ctx.bot.homelab_service.service_status()
    if not services:
        return "No facility services are configured."
    return "\n".join(f"{s['name']}: {'online' if s['online'] else 'OFFLINE'}"
                     + (f" ({s['ms']}ms)" if s['online'] else "") for s in services)


async def _printer_status(ctx: ToolContext) -> str:
    status = await ctx.bot.homelab_service.printer_status()
    if status is None:
        return "The 3D printer is unreachable or not configured."
    if status["state"] == "printing":
        return f"3D printer is printing {status['filename']} ({status['duration']} elapsed)."
    return f"3D printer state: {status['state']}."


async def _download_queue(ctx: ToolContext) -> str:
    items = await ctx.bot.homelab_service.download_queue()
    if not items:
        return "No active downloads."
    lines = [f"{i['source']}: {i['title']} - {i['status']} ({i['progress']})" for i in items[:10]]
    if len(items) > 10:
        lines.append(f"...and {len(items) - 10} more")
    return "\n".join(lines)


def build_cave_tools() -> ToolRegistry:
    return ToolRegistry([
        Tool(
            name="recommend_games",
            description="Recommend games from this server's game library. Use when someone asks what to play.",
            handler=_recommend_games,
            parameters={"type": "object", "properties": {
                "players": {"type": "integer", "description": "How many people will play (0 if unknown)"},
                "tag": {"type": "string", "description": "Optional genre/tag filter, e.g. survival, co-op"},
            }},
            requires_guild=True,
        ),
        Tool(
            name="list_game_tags",
            description="List the genre/tag names used in this server's game library.",
            handler=_list_game_tags,
            requires_guild=True,
        ),
        Tool(
            name="now_playing",
            description="Get the song currently playing (and queue size) in this server's voice channel.",
            handler=_now_playing,
            requires_guild=True,
        ),
        Tool(
            name="service_status",
            description="Check which homelab services (router, Pi-hole, Plex, server, printer) are online.",
            handler=_service_status,
            requires_auth=True,
        ),
        Tool(
            name="printer_status",
            description="Get the 3D printer's current state and job.",
            handler=_printer_status,
            requires_auth=True,
        ),
        Tool(
            name="download_queue",
            description="List active media downloads in Sonarr, Radarr and Lidarr.",
            handler=_download_queue,
            requires_auth=True,
        ),
    ])
