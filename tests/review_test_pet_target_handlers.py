"""Independent target-host review for PET action handlers.

The tests use temporary media and injected OS/network callables.  They never
open a real browser, play media, or contact an Ollama/cloud endpoint.
"""

import json
import os
from pathlib import Path

import pytest

from ai_ops_center import pet_target_handlers as handlers
from ai_ops_center import worker
from ai_ops_center.pet_machine_capabilities import CapabilityHeld


def _write(path: Path, value: bytes = b"test audio") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(value)
    return path


def test_music_listing_is_bounded_to_root_filters_extensions_and_exposes_no_paths(tmp_path, monkeypatch):
    root = tmp_path / "Music"
    included = _write(root / "Miles Davis - Blue in Green.MP3")
    _write(root / "notes.txt")
    _write(root / "payload.exe")
    monkeypatch.setenv("PET_MUSIC_LIBRARY_ROOT", str(root))

    result = handlers.list_music_library({})

    assert result["count"] == 1
    assert result["paths_included"] is False
    assert set(result["items"][0]) == {"id", "title", "artist"}
    assert result["items"][0]["title"] == "Blue in Green"
    assert result["items"][0]["artist"] == "Miles Davis"
    serialized = json.dumps(result)
    assert str(root) not in serialized
    assert str(included) not in serialized
    assert "notes.txt" not in serialized
    assert "payload.exe" not in serialized


def test_music_root_symlink_and_file_symlink_cannot_escape_library(tmp_path, monkeypatch):
    outside = tmp_path / "outside"
    secret = _write(outside / "Secret Artist - Secret Song.mp3")
    root = tmp_path / "Music"
    root.mkdir()
    linked_file = root / "linked-secret.mp3"
    try:
        linked_file.symlink_to(secret)
    except OSError as exc:
        pytest.skip(f"symlink creation unavailable: {exc}")
    monkeypatch.setenv("PET_MUSIC_LIBRARY_ROOT", str(root))

    assert handlers.list_music_library({})["items"] == []

    linked_root = tmp_path / "LinkedMusic"
    linked_root.symlink_to(outside, target_is_directory=True)
    monkeypatch.setenv("PET_MUSIC_LIBRARY_ROOT", str(linked_root))
    with pytest.raises(CapabilityHeld, match="symbolic link"):
        handlers.list_music_library({})


def test_music_index_rejects_resolved_candidate_outside_root_even_if_enumerated(tmp_path, monkeypatch):
    root = tmp_path / "Music"
    root.mkdir()
    outside = _write(tmp_path / "outside" / "Escaped - Track.mp3")
    monkeypatch.setenv("PET_MUSIC_LIBRARY_ROOT", str(root))
    original_rglob = Path.rglob

    def injected_rglob(path, pattern):
        if path.resolve() == root.resolve():
            return iter([outside])
        return original_rglob(path, pattern)

    monkeypatch.setattr(Path, "rglob", injected_rglob)

    result = handlers.list_music_library({})

    assert result["items"] == []
    assert str(outside) not in json.dumps(result)


def test_music_query_requires_one_unambiguous_match_and_launches_only_selected_file(tmp_path, monkeypatch):
    root = tmp_path / "Music"
    first = _write(root / "Artist One - Slow Down.mp3")
    second = _write(root / "Artist Two - Slow Down.flac")
    monkeypatch.setenv("PET_MUSIC_LIBRARY_ROOT", str(root))
    launched = []

    with pytest.raises(CapabilityHeld, match="ambiguous"):
        handlers.control_music({"command": "play", "media_query": "Slow Down"}, launcher=launched.append)
    assert launched == []

    listing = handlers.list_music_library({})
    selected = next(item for item in listing["items"] if item["artist"] == "Artist One")
    result = handlers.control_music({"command": "play", "media_id": selected["id"]}, launcher=launched.append)

    assert launched == [first.resolve()]
    assert launched[0] != second.resolve()
    assert result["id"] == selected["id"]
    assert result["path_included"] is False
    assert str(root) not in json.dumps(result)


def test_music_nonplay_commands_are_honestly_held_without_os_invocation(tmp_path, monkeypatch):
    root = tmp_path / "Music"
    _write(root / "Artist - Track.ogg")
    monkeypatch.setenv("PET_MUSIC_LIBRARY_ROOT", str(root))
    launched = []

    with pytest.raises(CapabilityHeld, match="not available"):
        handlers.control_music({"command": "pause"}, launcher=launched.append)
    assert launched == []


def test_browser_handler_uses_injected_os_opener_and_reports_rejection():
    calls = []

    result = handlers.open_browser(
        {"url": "https://www.youtube.com/"},
        opener=lambda url, **options: calls.append((url, options)) or True,
    )

    assert calls == [("https://www.youtube.com/", {"new": 2, "autoraise": True})]
    assert result == {"status": "launched", "target": "https://www.youtube.com/"}
    with pytest.raises(RuntimeError, match="did not accept"):
        handlers.open_browser({"url": "https://www.youtube.com/"}, opener=lambda *_args, **_kwargs: False)


class _FakeResponse:
    def __init__(self, payload: dict, final_url: str = "http://127.0.0.1:11434/api/chat") -> None:
        self.payload = json.dumps(payload).encode()
        self.final_url = final_url

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def read(self, _limit: int) -> bytes:
        return self.payload

    def geturl(self) -> str:
        return self.final_url


def test_device_model_posts_only_to_loopback_ollama_without_cloud_fallback(monkeypatch):
    monkeypatch.setenv("PET_DEVICE_OLLAMA_BASE_URL", "http://127.0.0.1:11434")
    calls = []

    def fake_urlopen(request, timeout):
        calls.append((request, timeout))
        return _FakeResponse({"message": {"content": "local reply"}})

    result = handlers.query_device_model(
        {"prompt": "Summarize queue health", "model_id": "llama3.2:3b"},
        urlopen=fake_urlopen,
    )

    request, timeout = calls[0]
    assert request.full_url == "http://127.0.0.1:11434/api/chat"
    assert request.method == "POST"
    assert json.loads(request.data)["messages"] == [{"role": "user", "content": "Summarize queue health"}]
    assert timeout <= 120
    assert result["provider"] == "ollama-local"
    assert result["cloud_fallback"] is False
    assert len(calls) == 1


@pytest.mark.parametrize(
    "base_url",
    [
        "https://127.0.0.1:11434",
        "http://8.8.8.8:11434",
        "http://example.com:11434",
        "http://user:pass@127.0.0.1:11434",
        "http://127.0.0.1:11434/proxy",
    ],
)
def test_device_model_rejects_nonlocal_or_ambiguous_origins_without_network(base_url, monkeypatch):
    monkeypatch.setenv("PET_DEVICE_OLLAMA_BASE_URL", base_url)
    calls = []
    with pytest.raises(CapabilityHeld, match="loopback|local-only"):
        handlers.query_device_model({"prompt": "hello"}, urlopen=lambda *args, **kwargs: calls.append((args, kwargs)))
    assert calls == []


def test_device_model_rejects_redirect_away_from_loopback(monkeypatch):
    monkeypatch.setenv("PET_DEVICE_OLLAMA_BASE_URL", "http://127.0.0.1:11434")

    with pytest.raises(CapabilityHeld, match="redirect|local-only|loopback"):
        handlers.query_device_model(
            {"prompt": "hello"},
            urlopen=lambda *_args, **_kwargs: _FakeResponse(
                {"message": {"content": "cloud reply"}},
                final_url="https://cloud.example/api/chat",
            ),
        )


def test_builtins_are_complete_but_worker_flags_default_disabled(monkeypatch):
    expected = {"browser_navigation", "music_playback", "music_library", "device_model_chat"}
    assert set(handlers.built_in_handlers()) == expected
    worker.MACHINE_CAPABILITY_HANDLERS.clear()
    for name in (
        "PET_ENABLE_BROWSER_NAVIGATION",
        "PET_ENABLE_MUSIC_PLAYBACK",
        "PET_ENABLE_MUSIC_LIBRARY",
        "PET_ENABLE_DEVICE_MODEL_CHAT",
    ):
        monkeypatch.delenv(name, raising=False)

    assert worker._enabled_machine_capability_handlers() == {}

    monkeypatch.setenv("PET_ENABLE_MUSIC_LIBRARY", "true")
    enabled = worker._enabled_machine_capability_handlers()
    assert set(enabled) == {"music_library"}
    assert enabled["music_library"] is handlers.list_music_library


def test_worker_registration_accepts_music_library_and_preserves_explicit_override(monkeypatch):
    worker.MACHINE_CAPABILITY_HANDLERS.clear()
    custom = lambda payload: {"custom": payload}
    worker.register_machine_capability_handler("music_library", custom)
    monkeypatch.setenv("PET_ENABLE_MUSIC_LIBRARY", "true")

    enabled = worker._enabled_machine_capability_handlers()

    assert enabled["music_library"] is custom
    worker.MACHINE_CAPABILITY_HANDLERS.clear()
