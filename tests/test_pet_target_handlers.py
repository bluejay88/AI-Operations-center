import json

import pytest

from ai_ops_center import pet_target_handlers as handlers
from ai_ops_center import worker
from ai_ops_center.pet_machine_capabilities import CapabilityHeld


def test_browser_handler_uses_injected_default_browser_opener() -> None:
    calls = []
    result = handlers.open_browser(
        {"url": "https://youtube.com"},
        opener=lambda url, **kwargs: calls.append((url, kwargs)) or True,
    )
    assert result == {"status": "launched", "target": "https://youtube.com"}
    assert calls == [("https://youtube.com", {"new": 2, "autoraise": True})]


def test_music_library_returns_opaque_metadata_without_paths(tmp_path, monkeypatch) -> None:
    (tmp_path / "Artist - Slow Down.mp3").write_bytes(b"not-real-audio")
    (tmp_path / "ignore.txt").write_text("not music", encoding="utf-8")
    monkeypatch.setenv("PET_MUSIC_LIBRARY_ROOT", str(tmp_path))
    result = handlers.list_music_library({})
    assert result["count"] == 1
    assert result["items"][0]["artist"] == "Artist"
    assert result["items"][0]["title"] == "Slow Down"
    assert len(result["items"][0]["id"]) == 24
    assert str(tmp_path) not in json.dumps(result)
    assert "path" not in result["items"][0]


def test_music_playback_resolves_index_and_holds_ambiguous_or_session_controls(tmp_path, monkeypatch) -> None:
    (tmp_path / "One - Slow Down.mp3").write_bytes(b"a")
    (tmp_path / "Two - Slow Down.flac").write_bytes(b"b")
    monkeypatch.setenv("PET_MUSIC_LIBRARY_ROOT", str(tmp_path))
    with pytest.raises(CapabilityHeld, match="ambiguous"):
        handlers.control_music({"command": "play", "media_query": "Slow Down"}, launcher=lambda path: None)
    with pytest.raises(CapabilityHeld, match="controllable playback session"):
        handlers.control_music({"command": "pause"}, launcher=lambda path: None)
    item = handlers.list_music_library({})["items"][0]
    launched = []
    result = handlers.control_music({"command": "play", "media_id": item["id"]}, launcher=launched.append)
    assert result["id"] == item["id"]
    assert len(launched) == 1


def test_device_model_rejects_cloud_and_calls_only_loopback_ollama(monkeypatch) -> None:
    monkeypatch.setenv("PET_DEVICE_OLLAMA_BASE_URL", "https://api.example.com")
    with pytest.raises(CapabilityHeld, match="loopback|local-only"):
        handlers.query_device_model({"prompt": "hello"}, urlopen=lambda *args, **kwargs: pytest.fail("must not call cloud"))

    class Response:
        def __enter__(self): return self
        def __exit__(self, *args): return None
        def read(self, limit): return json.dumps({"message": {"content": "Local answer"}}).encode()
        def geturl(self): return "http://127.0.0.1:11434/api/chat"

    calls = []
    monkeypatch.setenv("PET_DEVICE_OLLAMA_BASE_URL", "http://127.0.0.1:11434")
    monkeypatch.setenv("PET_DEVICE_OLLAMA_MODEL", "local-model")
    result = handlers.query_device_model(
        {"prompt": "hello", "model_id": "device-default"},
        urlopen=lambda request, **kwargs: calls.append((request, kwargs)) or Response(),
    )
    assert result["text"] == "Local answer"
    assert result["model"] == "local-model"
    assert result["cloud_fallback"] is False
    assert calls[0][0].full_url == "http://127.0.0.1:11434/api/chat"

    class Redirected(Response):
        def geturl(self): return "https://cloud.example/api/chat"

    with pytest.raises(CapabilityHeld, match="redirects are blocked"):
        handlers.query_device_model({"prompt": "hello"}, urlopen=lambda *args, **kwargs: Redirected())


def test_worker_registers_builtins_only_for_explicit_flags(monkeypatch) -> None:
    worker.MACHINE_CAPABILITY_HANDLERS.clear()
    for name in (
        "PET_ENABLE_BROWSER_NAVIGATION", "PET_ENABLE_MUSIC_LIBRARY",
        "PET_ENABLE_MUSIC_PLAYBACK", "PET_ENABLE_DEVICE_MODEL_CHAT",
    ):
        monkeypatch.delenv(name, raising=False)
    assert worker._enabled_machine_capability_handlers() == {}
    monkeypatch.setenv("PET_ENABLE_MUSIC_LIBRARY", "true")
    enabled = worker._enabled_machine_capability_handlers()
    assert set(enabled) == {"music_library"}
    assert enabled["music_library"] is handlers.list_music_library
