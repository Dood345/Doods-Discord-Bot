from unittest.mock import AsyncMock, MagicMock

from commands.music import MusicCommands
from services.music_library import MusicLibrary, PLEX_PREFIX, match_score


def plex_track(title, artist, key):
    return {"title": title, "grandparentTitle": artist, "Media": [{"Part": [{"key": key}]}]}


def library_with(responses):
    lib = MusicLibrary(base_url="http://plex.test:32400", token="tok")
    lib._get = AsyncMock(side_effect=lambda path, params=None: responses.get(path))
    return lib


def test_match_score_ignores_filler():
    assert match_score("play some Daft Punk", "Daft Punk") == 1.0
    assert match_score("still alive jonathan coulton", "Still Alive Jonathan Coulton") == 1.0
    assert match_score("still alive", "Still Alive (Lofi Remix) by xX_dj_Xx") == 1.0
    assert match_score("never gonna give you up", "Bohemian Rhapsody Queen") == 0.0


async def test_library_finds_best_matching_track():
    lib = library_with({"/hubs/search": {"Hub": [{"type": "track", "Metadata": [
        plex_track("Want You Gone", "Jonathan Coulton", "/library/parts/1/a.flac"),
        plex_track("Still Alive", "Jonathan Coulton", "/library/parts/2/b.flac"),
    ]}]}})
    assert await lib.find("still alive jonathan coulton") == (
        PLEX_PREFIX + "/library/parts/2/b.flac", "Still Alive", "Jonathan Coulton")


async def test_library_artist_request_picks_one_of_their_tracks():
    lib = library_with({
        "/hubs/search": {"Hub": [{"type": "track", "Metadata": []},
                                 {"type": "artist", "Metadata": [{"title": "Daft Punk", "ratingKey": "77"}]}]},
        "/library/metadata/77/allLeaves": {"Metadata": [plex_track("One More Time", "Daft Punk", "/library/parts/9/x.mp3")]},
    })
    assert await lib.find("play some daft punk") == (PLEX_PREFIX + "/library/parts/9/x.mp3", "One More Time", "Daft Punk")


async def test_library_rejects_weak_matches_and_needs_token():
    lib = library_with({"/hubs/search": {"Hub": [{"type": "track", "Metadata": [
        plex_track("Alive", "Pearl Jam", "/library/parts/3/c.flac")]}]}})
    assert await lib.find("still alive jonathan coulton") is None
    assert MusicLibrary(base_url="http://plex.test", token=None).available is False


def test_stream_source_keeps_token_out_of_url():
    lib = MusicLibrary(base_url="http://plex.test:32400", token="secret")
    url, before = lib.stream_source(PLEX_PREFIX + "/library/parts/2/b.flac")
    assert url == "http://plex.test:32400/library/parts/2/b.flac"
    assert "secret" not in url and "X-Plex-Token: secret" in before


def music_with(library=None, sc_entries=None, yt_info=None):
    music = MusicCommands(MagicMock(music_library=library))

    async def fetch(target):
        if target.startswith("scsearch"):
            return {"entries": sc_entries or []}
        return yt_info
    music._fetch_youtube_data = AsyncMock(side_effect=fetch)
    return music


async def test_routing_library_then_soundcloud_then_youtube():
    yt = {"_type": "playlist", "entries": [{"url": "https://youtube.com/watch?v=1", "title": "Still Alive", "uploader": "JC"}]}

    lib = MagicMock(available=True, find=AsyncMock(return_value=(PLEX_PREFIX + "/p", "Still Alive", "JC")))
    music = music_with(library=lib, yt_info=yt)
    assert (await music.resolve_track("still alive"))[0].startswith(PLEX_PREFIX)
    music._fetch_youtube_data.assert_not_awaited()             # library hit: no SoundCloud/YouTube calls

    lib.find.return_value = None
    sc = [{"url": "https://soundcloud.com/x/still-alive", "title": "Still Alive", "uploader": "JC"}]
    assert "soundcloud.com" in (await music_with(library=lib, sc_entries=sc, yt_info=yt).resolve_track("still alive"))[0]

    remix_only = [{"url": "https://soundcloud.com/x/other", "title": "Totally Different Song", "uploader": "dj"}]
    assert "youtube.com" in (await music_with(library=lib, sc_entries=remix_only, yt_info=yt).resolve_track("still alive"))[0]


async def test_youtube_links_skip_library_and_soundcloud():
    lib = MagicMock(available=True, find=AsyncMock())
    music = music_with(library=lib, yt_info={"url": "stream", "title": "Mix", "uploader": "DJ"})
    assert await music.resolve_track("https://www.youtube.com/watch?v=abc") == ("stream", "Mix", "DJ")
    lib.find.assert_not_awaited()
    assert MusicCommands.track_source(PLEX_PREFIX + "/p") == "📀 your library"


async def test_plex_is_searched_without_filler_words():
    lib = library_with({"/hubs/search": {"Hub": []}})
    await lib.find("play some Daft Punk please")
    assert lib._get.call_args_list[0].args[1]["query"] == "daft punk"


async def test_exact_artist_request_beats_featured_track():
    lib = library_with({
        "/hubs/search": {"Hub": [
            {"type": "track", "Metadata": [plex_track("Juicy Sweatsuits", "blackbear feat. Juicy J", "/p/feat")]},
            {"type": "artist", "Metadata": [{"title": "Juicy J", "ratingKey": "5"}]}]},
        "/library/metadata/5/allLeaves": {"Metadata": [plex_track("Bandz a Make Her Dance", "Juicy J", "/p/own")]},
    })
    assert (await lib.find("play some Juicy J"))[0] == PLEX_PREFIX + "/p/own"
