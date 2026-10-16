from utils import config_report
from utils.config_report import BotConfig, feature_states, warnings


def test_features_report_missing_settings_by_name(monkeypatch):
    monkeypatch.setattr(BotConfig, "OLLAMA_URL", "http://ollama:11434")
    monkeypatch.setattr(BotConfig, "OLLAMA_EMBED_MODEL", None)
    monkeypatch.setattr(BotConfig, "PLEX_TOKEN", None)
    rows = {name: (on, note) for name, on, note in feature_states()}
    assert rows["AI chat (Cave)"] == (True, "")
    assert rows["Recall of old chats"] == (False, "set OLLAMA_EMBED_MODEL")
    assert rows["Music library (Plex)"][0] is False and "PLEX_TOKEN" in rows["Music library (Plex)"][1]


def test_warnings_catch_known_traps(monkeypatch):
    monkeypatch.setattr(BotConfig, "PRINTER_WEBCAM_URL", "http://cam/webcam/?action=stream")
    monkeypatch.setattr(BotConfig, "OVERSEERR_URL", "overseerr.local:5055")
    monkeypatch.setattr(BotConfig, "BOT_TIMEZONE", "Mars/Olympus_Mons")
    found = " | ".join(warnings())
    assert "action=snapshot" in found and "OVERSEERR_URL should start with http" in found and "Mars/Olympus_Mons" in found


def test_report_never_logs_values(monkeypatch, caplog):
    monkeypatch.setattr(BotConfig, "PLEX_TOKEN", "super-secret-token")
    monkeypatch.setattr(BotConfig, "OVERSEERR_API_KEY", "another-secret")
    with caplog.at_level("INFO", logger=config_report.__name__):
        config_report.log_report()
    assert "super-secret-token" not in caplog.text and "another-secret" not in caplog.text
    assert "Features on" in caplog.text
