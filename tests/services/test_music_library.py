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
    assert MusicCommands.track_source(PLEX_PREFIX + "/p") == "📀 the facility archives"


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


def artist_library(own_count, similar=None):
    responses = {
        "/hubs/search": {"Hub": [{"type": "artist", "Metadata": [{"title": "311", "ratingKey": "1"}]},
                                 {"type": "track", "Metadata": [
                                     dict(plex_track("Amber", "311", "/p/amber"), grandparentRatingKey="1")]}]},
        "/library/metadata/1/allLeaves": {"Metadata": [plex_track(f"Song {i}", "311", f"/p/{i}") for i in range(own_count)]},
        "/library/metadata/1/similar": {"Metadata": [{"title": n, "ratingKey": n} for n in (similar or [])]},
    }
    for n in similar or []:
        responses[f"/library/metadata/{n}/allLeaves"] = {"Metadata": [plex_track(f"{n} hit {i}", n, f"/p/{n}{i}") for i in range(5)]}
    return library_with(responses)


async def test_artist_request_becomes_shuffled_mix():
    tracks, description = await artist_library(17).plan("play some 311")
    assert len(tracks) == 10 and len({t[0] for t in tracks}) == 10
    assert all(t[2] == "311" for t in tracks) and "10-track **311** mix" in description


async def test_small_artist_or_radio_request_mixes_in_similar_artists():
    tracks, description = await artist_library(1, similar=["Sublime", "Incubus"]).plan("311")
    assert "radio" in description and tracks[0][2] == "311"
    assert {t[2] for t in tracks} >= {"Sublime", "Incubus"}

    tracks, _ = await artist_library(17, similar=["Sublime"]).plan("311 radio", radio=True)
    assert 1 < sum(t[2] == "311" for t in tracks) <= 5 and any(t[2] == "Sublime" for t in tracks)


async def test_song_radio_starts_with_that_song():
    tracks, description = await artist_library(17, similar=["Sublime"]).plan("amber 311", radio=True)
    assert tracks[0][0] == PLEX_PREFIX + "/p/amber" and "starting with **Amber**" in description
    assert PLEX_PREFIX + "/p/amber" not in [t[0] for t in tracks[1:]]
    tracks, _ = await artist_library(17).plan("amber 311")
    assert [t[1] for t in tracks] == ["Amber"]


async def test_enqueue_tracks_queues_all_and_starts_playing():
    from types import SimpleNamespace
    music = MusicCommands(MagicMock(music_library=None))
    music.play_next = AsyncMock()
    vc = MagicMock(channel=SimpleNamespace(id=7, name="Lounge"))
    vc.is_playing.return_value = vc.is_paused.return_value = False
    channel = SimpleNamespace(id=7, name="Lounge")
    member = SimpleNamespace(voice=SimpleNamespace(channel=channel), guild=SimpleNamespace(voice_client=vc))
    tracks = [("u1", "A", "x"), ("u2", "B", "x"), ("u3", "C", "x")]

    msg = await music.enqueue_tracks(member, None, tracks)
    assert music.players[7].queue == tracks and "+2 more" in msg
    music.play_next.assert_awaited_once()


def test_title_score_and_best_album():
    from services.music_library import best_album, title_score
    assert title_score("Still Alive Jonathan Coulton", "Still Alive") == 1.0
    assert title_score("Still Alive Jonathan Coulton", "Still Alive (J.C. mix)") == 0.0   # extra title words
    assert title_score("play the whole portal two soundtrack today", "Alive") == 0.0        # too small a part
    albums = [{"title": "Portal 2 Soundtrack: Songs to Test By", "parentTitle": "Aperture"},
              {"title": "Portal Original Soundtrack", "parentTitle": "Aperture"},
              {"title": "Half-Life 2", "parentTitle": "Valve"}]
    assert best_album("Portal Soundtrack", albums)["title"] == "Portal Original Soundtrack"
    assert best_album("portal 2 soundtrack", albums)["title"].startswith("Portal 2")
    assert best_album("kryptonite", albums) is None


async def test_search_retries_shorter_phrases():
    from unittest.mock import AsyncMock
    from services.music_library import MusicLibrary
    lib = MusicLibrary(base_url="http://plex", token="t")
    hit = {"Hub": [{"type": "track", "Metadata": [{"title": "Still Alive"}]}]}
    lib._get = AsyncMock(side_effect=[{"Hub": []}, {"Hub": []}, hit])
    hubs = await lib._search("still alive jonathan coulton")
    assert hubs["track"][0]["title"] == "Still Alive"
    assert [c.args[1]["query"] for c in lib._get.await_args_list] == [
        "still alive jonathan coulton", "still alive jonathan", "still alive"]
    lib._get = AsyncMock(return_value=None)
    assert await lib._search("anything here") is None                 # Plex down: no retries
