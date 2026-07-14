from __future__ import annotations

import hashlib
import ipaddress
import json
import os
import re
import subprocess
import sys
import urllib.request
import urllib.error
import webbrowser
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlsplit

from .pet_machine_capabilities import CapabilityHeld


AUDIO_EXTENSIONS = frozenset({".mp3", ".wav", ".flac", ".m4a", ".aac", ".ogg", ".wma"})
_SAFE_MODEL = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")


def open_browser(payload: dict[str, Any], opener: Callable[..., bool] = webbrowser.open) -> dict[str, Any]:
    url = str(payload["url"])
    if not opener(url, new=2, autoraise=True):
        raise RuntimeError("The operating system did not accept the browser request.")
    return {"status": "launched", "target": url}


def list_music_library(payload: dict[str, Any]) -> dict[str, Any]:
    if payload:
        raise CapabilityHeld("Music-library queries do not accept additional fields.")
    entries = _music_index()
    return {
        "count": len(entries),
        "items": [{key: item[key] for key in ("id", "title", "artist")} for item in entries],
        "paths_included": False,
    }


def control_music(payload: dict[str, Any], launcher: Callable[[Path], None] | None = None) -> dict[str, Any]:
    command = str(payload.get("command") or "")
    if command != "play":
        raise CapabilityHeld(f"Music command {command!r} requires a controllable playback session, which is not available.")
    entries = _music_index(include_paths=True)
    media_id = str(payload.get("media_id") or "").strip()
    query = str(payload.get("media_query") or "").strip()
    if media_id:
        matches = [item for item in entries if item["id"] == media_id]
    else:
        needle = _normalize(query)
        matches = [item for item in entries if needle and needle in item["search"]]
    if not matches:
        raise CapabilityHeld("No matching item was found in the configured local music library.")
    if len(matches) > 1:
        raise CapabilityHeld("The music query is ambiguous; list the library and select an opaque media ID.")
    selected = matches[0]
    (launcher or _launch_local_file)(selected["_path"])
    return {"status": "launched", "id": selected["id"], "title": selected["title"], "artist": selected["artist"], "path_included": False}


def query_device_model(payload: dict[str, Any], urlopen: Callable[..., Any] | None = None) -> dict[str, Any]:
    base_url = os.getenv("PET_DEVICE_OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/")
    parsed = urlsplit(base_url)
    if parsed.scheme != "http" or not parsed.hostname or parsed.username or parsed.password or parsed.path not in {"", "/"}:
        raise CapabilityHeld("Device model endpoint must be a plain loopback HTTP origin.")
    try:
        address = ipaddress.ip_address(parsed.hostname)
        loopback = address.is_loopback
    except ValueError:
        loopback = parsed.hostname.lower() == "localhost"
    if not loopback:
        raise CapabilityHeld("Device model endpoint must remain local-only; cloud fallback is disabled.")
    requested_model = str(payload.get("model_id") or "")
    model = os.getenv("PET_DEVICE_OLLAMA_MODEL", "device-default") if requested_model in {"", "device-default"} else requested_model
    if not _SAFE_MODEL.fullmatch(model):
        raise CapabilityHeld("Device model identifier is invalid.")
    timeout = max(1.0, min(float(os.getenv("PET_DEVICE_OLLAMA_TIMEOUT_SECONDS", "60")), 120.0))
    request = urllib.request.Request(
        f"{base_url}/api/chat",
        data=json.dumps({
            "model": model,
            "stream": False,
            "messages": [{"role": "user", "content": str(payload["prompt"])}],
        }).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    expected_url = f"{base_url}/api/chat"
    try:
        with (urlopen or _local_urlopen)(request, timeout=timeout) as response:
            final_url = response.geturl() if hasattr(response, "geturl") else expected_url
            if final_url != expected_url:
                raise CapabilityHeld("Device model redirects are blocked to preserve the local-only boundary.")
            result = json.loads(response.read(2_000_000).decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if 300 <= exc.code < 400:
            raise CapabilityHeld("Device model redirects are blocked to preserve the local-only boundary.") from exc
        raise
    text = str((result.get("message") or {}).get("content") or result.get("response") or "").strip()
    if not text:
        raise RuntimeError("The local device model returned no response text.")
    return {"status": "completed", "provider": "ollama-local", "model": model, "text": text[:4000], "cloud_fallback": False}


def built_in_handlers() -> dict[str, Callable[[dict[str, Any]], dict[str, Any]]]:
    return {
        "browser_navigation": open_browser,
        "music_library": list_music_library,
        "music_playback": control_music,
        "device_model_chat": query_device_model,
    }


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001
        return None


def _local_urlopen(request: urllib.request.Request, timeout: float) -> Any:
    return urllib.request.build_opener(_NoRedirect()).open(request, timeout=timeout)


def _music_root() -> Path:
    configured = os.getenv("PET_MUSIC_LIBRARY_ROOT", "").strip()
    root = Path(configured).expanduser() if configured else Path.home() / "Music"
    if root.is_symlink():
        raise CapabilityHeld("The configured music-library root cannot be a symbolic link.")
    resolved = root.resolve()
    if not resolved.exists() or not resolved.is_dir():
        raise CapabilityHeld("The configured local music library is unavailable.")
    return resolved


def _music_index(include_paths: bool = False) -> list[dict[str, Any]]:
    root = _music_root()
    entries: list[dict[str, Any]] = []
    for candidate in root.rglob("*"):
        if len(entries) >= 2000:
            break
        if candidate.is_symlink() or not candidate.is_file() or candidate.suffix.lower() not in AUDIO_EXTENSIONS:
            continue
        resolved = candidate.resolve()
        try:
            relative = resolved.relative_to(root)
        except ValueError:
            continue
        artist, title = _display_metadata(candidate)
        opaque_id = hashlib.sha256(relative.as_posix().encode("utf-8")).hexdigest()[:24]
        item: dict[str, Any] = {
            "id": opaque_id,
            "title": title,
            "artist": artist,
            "search": _normalize(f"{artist} {title} {candidate.stem}"),
        }
        if include_paths:
            item["_path"] = resolved
        entries.append(item)
    entries.sort(key=lambda item: (item["artist"].casefold(), item["title"].casefold(), item["id"]))
    return entries


def _display_metadata(path: Path) -> tuple[str, str]:
    stem = _clean(path.stem)
    if " - " in stem:
        artist, title = stem.split(" - ", 1)
        return _clean(artist), _clean(title)
    return "Unknown artist", stem


def _clean(value: str) -> str:
    return " ".join("".join(character if character.isprintable() else " " for character in value).split())[:160] or "Unknown"


def _normalize(value: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", value.casefold()))


def _launch_local_file(path: Path) -> None:
    if sys.platform == "win32":
        os.startfile(str(path))  # type: ignore[attr-defined]
        return
    command = ["open", str(path)] if sys.platform == "darwin" else ["xdg-open", str(path)]
    subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, close_fds=True)
