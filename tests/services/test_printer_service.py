from unittest.mock import AsyncMock

from config import printer_address
import services.printer_service as printer_module
from services.printer_service import PrinterService, describe, parse_status

PRINTING = {
    "print_stats": {"filename": "benchy/3DBenchy_PLA_1h.gcode", "print_duration": 1800.0, "state": "printing",
                    "message": "", "info": {"total_layer": 120, "current_layer": 30}},
    "display_status": {"progress": 0.25},
    "virtual_sdcard": {"progress": 0.24},
    "extruder": {"temperature": 219.6, "target": 220.0},
    "heater_bed": {"temperature": 59.9, "target": 60.0},
    "heater_generic chamber": {"temperature": 35.2, "target": 0.0},
    "filament_switch_sensor filament": {"filament_detected": True, "enabled": True},
}


def test_parse_printing_status():
    s = parse_status(PRINTING)
    assert (s["state"], s["filename"], s["progress"]) == ("printing", "3DBenchy_PLA_1h", 25)
    assert (s["duration"], s["remaining"], s["layer"]) == ("0h 30m", "1h 30m", (30, 120))
    assert s["temps"] == {"nozzle": (220, 220), "bed": (60, 60), "chamber": (35, 0)}
    text = describe(s)
    assert "25% done" in text and "about 1h 30m left" in text and "layer 30/120" in text and "nozzle 220°C/220°C" in text


def test_parse_idle_and_runout():
    s = parse_status({"print_stats": {"state": "standby", "filename": ""},
                      "filament_switch_sensor filament": {"filament_detected": False, "enabled": True}})
    assert s["remaining"] is None and s["filename"] is None and s["layer"] is None
    assert describe(s) == "standby. ⚠️ Filament sensor reports NO filament."
    # Too early to estimate time left
    early = dict(PRINTING, display_status={"progress": 0.01})
    assert parse_status(early)["remaining"] is None


async def test_webcam_discovery_and_override(monkeypatch):
    monkeypatch.setattr(printer_module.BotConfig, "PRINTER_WEBCAM_URL", None)
    p = PrinterService(ip="10.0.0.5", port=80)
    p._get_json = AsyncMock(return_value={"webcams": [
        {"enabled": False, "snapshot_url": "/off", "stream_url": "/off"},
        {"enabled": True, "snapshot_url": "/webcam/?action=snapshot", "stream_url": "/webcam/?action=stream"}]})
    cam = await p.webcam()
    assert cam == {"snapshot": "http://10.0.0.5:80/webcam/?action=snapshot", "stream": "http://10.0.0.5:80/webcam/?action=stream"}
    await p.webcam()
    p._get_json.assert_awaited_once()  # cached

    monkeypatch.setattr(printer_module.BotConfig, "PRINTER_WEBCAM_URL", "http://cam.local/webcam/?action=stream")
    cam = await PrinterService(ip="10.0.0.5").webcam()
    assert cam["snapshot"].endswith("action=snapshot") and cam["stream"].endswith("action=stream")


async def test_unconfigured_printer():
    p = PrinterService(ip="", port=80)
    assert not p.configured and await p.status() is None


def test_printer_address_from_env():
    assert printer_address({"PRINTER_IP": "10.0.0.5"}) == ("10.0.0.5", 80)
    assert printer_address({"PRINTER_IP": "10.0.0.5", "PRINTER_PORT": "7125"}) == ("10.0.0.5", 7125)
    assert printer_address({"PRINTER_HOST": " 10.0.0.6:7125 "}) == ("10.0.0.6", 7125)   # legacy .env
    assert printer_address({"PRINTER_IP": "10.0.0.5", "PRINTER_HOST": "10.0.0.6:7125"}) == ("10.0.0.5", 7125)
    assert printer_address({}) == (None, 80)
