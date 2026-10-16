"""Tools Cave Johnson can call from chat. Each wraps an existing service; no business logic here.

Tool output is read back to the user in a (possibly public) channel: never include IPs, hostnames or keys.
"""

import io

import discord

from utils.agent import Tool, ToolContext, ToolRegistry
from utils.auth import is_authorized
from utils.confirm import post_confirmation
from utils.members import member_name


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


async def _skip_song(ctx: ToolContext) -> str:
    music = ctx.bot.get_cog("MusicCommands")
    if music is None:
        return "The music system is offline."
    vc = ctx.guild.voice_client
    if not vc or not getattr(vc, "channel", None):
        return "Nothing is playing in this server."
    voice = getattr(ctx.user, "voice", None)
    if not voice or not voice.channel or voice.channel.id != vc.channel.id:
        return "ERROR: only someone in the same voice channel as the music can skip it."
    track = music.skip_current(ctx.guild)
    if track is None:
        return "Nothing is playing right now."
    return f"Skipped {track[1]}" + (f" by {track[2]}" if track[2] else "") + ". The next track in the queue (if any) is starting."


async def _rate_game(ctx: ToolContext, title: str, score: int) -> str:
    try:
        score = int(score)
    except (TypeError, ValueError):
        return "ERROR: the score must be a whole number from 1 to 10."
    title = " ".join(str(title).split())[:100]
    matches = await ctx.bot.db.search_game_titles(title, ctx.guild.id) if title else []
    exact = [m for m in matches if m.lower() == title.lower()]
    if exact or len(matches) == 1:
        chosen = (exact or matches)[0]
    elif matches:
        return "ERROR: several games match; ask which one they meant: " + ", ".join(matches[:8])
    else:
        return f"ERROR: '{title}' isn't in this server's game library. They can add it first."
    _, msg = await ctx.bot.game_service.rate_game(chosen, score, ctx.user.id, ctx.guild.id)
    return msg


async def _science_points(ctx: ToolContext) -> str:
    points_service = getattr(ctx.bot, "points_service", None)
    if points_service is None:
        return "The Science Points system is offline."
    points, rank, achievements = await points_service.profile(ctx.guild.id, ctx.user.id)
    mine = (f"{ctx.user.display_name} has {points} Science Points (rank #{rank})"
            + (f" and achievements: {', '.join(a.name for a in achievements)}" if achievements else "")
            if points > 0 else f"{ctx.user.display_name} has no Science Points yet")
    board = await points_service.leaderboard(ctx.guild.id, limit=5)
    names = []
    for i, (uid, pts) in enumerate(board, 1):
        names.append(f"{i}. {await member_name(ctx.guild, uid)} ({pts})")
    return mine + ". Top of this server's leaderboard: " + ("; ".join(names) if names else "nobody yet") + "."


def _to_int(value, default: int) -> int:
    try:
        return max(1, min(int(value), 100))
    except (TypeError, ValueError):
        return default


# --- Side-effecting tools: each posts a confirm card; the action runs only when ctx.user clicks ---

async def _add_game(ctx: ToolContext, title: str = None, min_players: int = None, max_players: int = None,
                    tags: str = None, link: str = None) -> str:
    extra = {}
    if link:
        # Store data beats the model's guesses; the model's values only fill gaps
        info = await ctx.bot.game_service.details_from_link(str(link))
        if info is None:
            return "ERROR: that isn't a Steam or Epic store link. Ask for the game's name instead."
        guessed = info.pop("players_guessed", False)
        title = info.pop("title", None) or title
        if not guessed or min_players is None:
            min_players = info.pop("min_players", min_players)
        if not guessed or max_players is None:
            max_players = info.pop("max_players", max_players)
        tags = info.pop("tags", None) or tags
        extra = {k: v for k, v in info.items() if k in ("store_link", "release_state", "release_date",
                                                         "external_rating", "category") and v}
    title = " ".join(str(title or "").split())[:100]
    if not title:
        return "ERROR: a game title (or a Steam/Epic store link) is required."
    lo, hi = _to_int(min_players, 1), _to_int(max_players, 4)
    lo, hi = min(lo, hi), max(lo, hi)
    tags = str(tags)[:200] if tags else None
    guild_id, user_id = ctx.guild.id, ctx.user.id

    async def action(interaction):
        _, msg = await ctx.bot.game_service.add_game(title, user_id, guild_id, lo, hi, tags=tags, **extra)
        return msg

    tag_text = f", tags: {tags}" if tags else ""
    if extra.get("external_rating"):
        tag_text += f", {extra['external_rating']}"
    return await post_confirmation(
        ctx, f"add_game:{title.lower()}",
        f"🎮 {ctx.user.display_name}, add **{title}** ({lo}-{hi} players{tag_text}) to the game library?",
        action, confirm_label="Add game")


async def _search_media(ctx: ToolContext, query: str) -> str:
    results = await ctx.bot.homelab_service.search_media(str(query)[:100])
    if results is None:
        return "ERROR: the media server (Overseerr) is not responding right now. Nothing was searched or requested."
    if not results:
        return f"No movies or shows found for '{query}'."
    return "Search results (use tmdb_id + media_type with request_media):\n" + "\n".join(
        f"- {r['title']} ({r['year']}) [{r['media_type']}] tmdb_id={r['tmdb_id']}" for r in results)


async def _request_media(ctx: ToolContext, tmdb_id: int, media_type: str) -> str:
    media_type = str(media_type).lower()
    if media_type not in ("movie", "tv"):
        return "ERROR: media_type must be 'movie' or 'tv'."
    try:
        tmdb_id = int(tmdb_id)
    except (TypeError, ValueError):
        return "ERROR: tmdb_id must be a number from search_media."
    details = await ctx.bot.homelab_service.media_details(tmdb_id, media_type)
    if details is None:
        return "ERROR: couldn't find that title. Run search_media first and use its tmdb_id."

    async def check(interaction):
        # Re-check on click: clearance can change and only the human who clicked counts
        if not is_authorized(interaction.user):
            return "❌ **Access Denied**: Authorized Personnel Only ⛔"
        return None

    async def action(interaction):
        status, title = await ctx.bot.homelab_service.request_media(tmdb_id, media_type)
        return {"requested": f"✅ Requested **{title}**! The download goblins have been dispatched.",
                "duplicate": f"⚠️ **{title}** is already requested."}.get(status, "❌ The request failed. Check the logs.")

    kind = "movie" if media_type == "movie" else "TV show"
    return await post_confirmation(
        ctx, f"request_media:{media_type}:{tmdb_id}",
        f"📥 {ctx.user.display_name}, request the {kind} **{details['title']} ({details['year']})**?",
        action, check=check, confirm_label="Request")


async def _queue_song(ctx: ToolContext, query: str, radio: bool = False) -> str:
    music = ctx.bot.get_cog("MusicCommands")
    if music is None:
        return "The music system is offline."
    if not isinstance(ctx.user, discord.Member) or not ctx.user.voice or not ctx.user.voice.channel:
        return "ERROR: the user must join a voice channel first."
    planned = await music.resolve_request(str(query)[:200], radio=bool(radio))
    if isinstance(planned, str):
        return f"ERROR: {planned}"
    tracks, description = planned
    url = tracks[0][0]
    preview = ""
    if len(tracks) > 1:
        preview = "\n" + "\n".join(f"• {t[1]} — {t[2]}" for t in tracks[:4])
        if len(tracks) > 4:
            preview += f"\n• …and {len(tracks) - 4} more"

    async def check(interaction):
        member = interaction.guild.get_member(interaction.user.id) if interaction.guild else None
        if not member or not member.voice or not member.voice.channel:
            return "🎙️ Join a voice channel first, then click again... oh wait, you can't. Ask me again."
        return None

    async def action(interaction):
        member = interaction.guild.get_member(interaction.user.id)
        return await music.enqueue_tracks(member, interaction.channel, tracks)

    return await post_confirmation(
        ctx, f"queue_song:{url}:{len(tracks)}",
        f"🎵 {ctx.user.display_name}, queue {description}? ({music.track_source(url)}){preview}",
        action, check=check, confirm_label="Queue it")


async def _generate_image(ctx: ToolContext, prompt: str) -> str:
    images = getattr(ctx.bot, "image_service", None)
    if images is None or ctx.channel is None:
        return "ERROR: image generation isn't available here."
    prompt = " ".join(str(prompt).split())[:500]
    if not prompt:
        return "ERROR: describe the image to generate."
    if key := images.check_available(ctx.user.id):
        return {"busy": "ERROR: the image generator is busy with another job; try again in a minute.",
                "cooldown": "ERROR: this user generated an image less than a minute ago; ask them to wait."}[key]

    channel, user_id, dialogue = ctx.channel, ctx.user.id, ctx.bot.dialogue

    async def job():
        # Chat-initiated prompts weren't typed into /imagine, so the safety filter fails closed
        result = await images.generate(user_id, prompt, fail_closed=True)
        if result.status == "ok":
            await channel.send(
                dialogue.get("system", "image_success", prompt=prompt, enhanced_prompt=result.enhanced_prompt),
                file=discord.File(io.BytesIO(result.image), filename="generated.png"))
        elif result.status == "refused":
            await channel.send(dialogue.get("system", "image_denied"))
        else:
            await channel.send(dialogue.get("system", f"image_{result.status}"))

    images.run_in_background(job())
    return ("STARTED: the image is generating and will be posted in this channel in about a minute. "
            "Tell the user it's on the way; do not describe it as finished.")


async def _remember_fact(ctx: ToolContext, fact: str) -> str:
    status = await ctx.bot.db.add_user_fact(ctx.user.id, str(fact))
    return {
        "added": "Saved to this user's permanent file.",
        "duplicate": "Already in this user's file.",
        "full": "This user's file is full (20 notes). They can wipe it with /clearhistory.",
    }.get(status, "ERROR: couldn't save that.")


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
            name="skip_song",
            description="Skip the song currently playing in this server's voice channel.",
            handler=_skip_song,
            requires_guild=True,
        ),
        Tool(
            name="rate_game",
            description="Record the user's own rating (1-10) for a game in this server's game library.",
            handler=_rate_game,
            parameters={"type": "object", "properties": {
                "title": {"type": "string", "description": "The game's name"},
                "score": {"type": "integer", "description": "Rating from 1 to 10"},
            }, "required": ["title", "score"]},
            requires_guild=True,
        ),
        Tool(
            name="science_points",
            description="The user's Science Points, rank and achievements in this server, plus the top of the leaderboard.",
            handler=_science_points,
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
        Tool(
            name="add_game",
            description="Add a game to this server's game library by name or Steam/Epic store link "
                        "(a link fills in the details automatically; the user confirms with a button).",
            handler=_add_game,
            parameters={"type": "object", "properties": {
                "title": {"type": "string"},
                "link": {"type": "string", "description": "Steam or Epic store link, if they gave one"},
                "min_players": {"type": "integer"},
                "max_players": {"type": "integer"},
                "tags": {"type": "string", "description": "Comma-separated tags, e.g. 'survival, co-op'"},
            }},
            requires_guild=True,
            timeout=20,
        ),
        Tool(
            name="queue_song",
            description="Play music in the user's voice channel (the user confirms with a button). "
                        "A song or YouTube link queues that song; just an artist's name queues a mix of their songs; "
                        "radio=true starts a radio station of similar music.",
            handler=_queue_song,
            parameters={"type": "object", "properties": {
                "query": {"type": "string", "description": "Song, artist, or YouTube link, e.g. 'Still Alive Jonathan Coulton' or '311'"},
                "radio": {"type": "boolean", "description": "true if they ask for a radio/station/similar music"},
            }, "required": ["query"]},
            requires_guild=True,
            timeout=45,  # yt-dlp lookups can be slow
        ),
        Tool(
            name="search_media",
            description="Search movies and TV shows on the media server. Use before request_media.",
            handler=_search_media,
            parameters={"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]},
            requires_auth=True,
        ),
        Tool(
            name="request_media",
            description="Request a movie or TV show for download (the user confirms with a button). "
                        "Use a tmdb_id and media_type from search_media.",
            handler=_request_media,
            parameters={"type": "object", "properties": {
                "tmdb_id": {"type": "integer"},
                "media_type": {"type": "string", "enum": ["movie", "tv"]},
            }, "required": ["tmdb_id", "media_type"]},
            requires_auth=True,
            timeout=20,
        ),
        Tool(
            name="generate_image",
            description="Generate an image from a description and post it in this channel (takes about a minute).",
            handler=_generate_image,
            parameters={"type": "object", "properties": {
                "prompt": {"type": "string", "description": "What the image should show"},
            }, "required": ["prompt"]},
        ),
        Tool(
            name="remember_fact",
            description="Save a short note about the current user to remember in future chats "
                        "(e.g. 'loves Valheim', 'hates horror games').",
            handler=_remember_fact,
            parameters={"type": "object", "properties": {"fact": {"type": "string"}}, "required": ["fact"]},
        ),
    ])
