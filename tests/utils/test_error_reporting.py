from types import SimpleNamespace
from unittest.mock import AsyncMock

import discord

from utils.error_reporting import RATE_LIMIT_SECONDS, ErrorReporter, handle_app_command_error, scrub


def boom(message="Plex request failed"):
    try:
        raise RuntimeError(message)
    except RuntimeError as e:
        return e


def test_scrub_removes_secrets_urls_and_ips():
    text = ("GET http://10.0.0.5:32400/library?X-Plex-Token=abc123 failed; api_key=sk-999 token: zzz "
            "host 10.0.0.5:7125 key=hunter2")
    out = scrub(text)
    for secret in ("abc123", "sk-999", "zzz", "10.0.0.5", "hunter2", "32400"):
        assert secret not in out, secret
    assert "[url]" in out and "[ip]" in out


async def test_report_dms_owner_once_per_window():
    owner = SimpleNamespace(send=AsyncMock())
    now = [1000.0]
    bot = SimpleNamespace(get_user=lambda uid: owner)
    reporter = ErrorReporter(bot, owner_id=42, clock=lambda: now[0])

    err = boom("token=secret123 at http://10.0.0.9/x")
    assert await reporter.report("/printer", err, "Dood")
    text = owner.send.call_args.args[0]
    assert "/printer" in text and "RuntimeError" in text and "Dood" in text
    assert "secret123" not in text and "10.0.0.9" not in text and len(text) <= 2000

    assert not await reporter.report("/printer", err)           # same problem, inside the window
    assert await reporter.report("/play", boom())               # different place: reported
    now[0] += RATE_LIMIT_SECONDS + 1
    assert await reporter.report("/printer", err)               # window passed
    assert owner.send.await_count == 3


async def test_no_owner_configured_still_logs():
    reporter = ErrorReporter(SimpleNamespace(), owner_id=0)
    assert not await reporter.report("/x", boom())


async def test_app_command_error_tells_user_and_reports():
    reporter = SimpleNamespace(report=AsyncMock())
    sent = AsyncMock()
    interaction = SimpleNamespace(
        command=SimpleNamespace(qualified_name="printer"), user="Dood",
        response=SimpleNamespace(is_done=lambda: False, send_message=sent),
        followup=SimpleNamespace(send=AsyncMock()))
    error = discord.app_commands.CommandInvokeError(SimpleNamespace(name="printer", qualified_name="printer"), boom())
    await handle_app_command_error(reporter, interaction, error)
    where, original, user = reporter.report.call_args.args
    assert where == "/printer" and isinstance(original, RuntimeError) and user == "Dood"
    assert sent.call_args.kwargs["ephemeral"] is True


async def test_expected_failures_are_not_reported():
    reporter = SimpleNamespace(report=AsyncMock())
    followup = AsyncMock()
    interaction = SimpleNamespace(command=None, user="x", response=SimpleNamespace(is_done=lambda: True),
                                  followup=SimpleNamespace(send=followup))
    await handle_app_command_error(reporter, interaction, discord.app_commands.CheckFailure())
    reporter.report.assert_not_awaited()
    assert followup.call_args.kwargs["ephemeral"] is True
