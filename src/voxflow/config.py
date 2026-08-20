from __future__ import annotations

import shutil
import tomllib
from pathlib import Path
from typing import Any


def _resolve(base: Path, value: str) -> str:
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = (base / path).resolve()
    return str(path)


def load_config(path: str | Path) -> dict[str, Any]:
    config_path = Path(path).resolve()
    with config_path.open("rb") as handle:
        data = tomllib.load(handle)
    base = config_path.parent
    paths = data.setdefault("paths", {})
    for key in ("whiteboard_root", "vox_director_root", "projects_root"):
        paths[key] = _resolve(base, paths[key])
    assembly = data.setdefault("assembly", {})
    if assembly.get("bgm"):
        assembly["bgm"] = _resolve(base, assembly["bgm"])
    data["_config_path"] = str(config_path)
    return data


def doctor(settings: dict[str, Any]) -> dict[str, Any]:
    whiteboard = Path(settings["paths"]["whiteboard_root"])
    vox_director = Path(settings["paths"]["vox_director_root"])
    image_script = whiteboard / "skills/whiteboard-video-workflow/scripts/generate-image.py"
    tts_script = whiteboard / "auto-whiteboard/scripts/generate_voiceover.py"
    whiteboard_python = whiteboard / ".venv/Scripts/python.exe"
    if not whiteboard_python.exists():
        whiteboard_python = Path(shutil.which("python") or "python")
    return {
        "ffmpeg": bool(shutil.which("ffmpeg")),
        "ffprobe": bool(shutil.which("ffprobe")),
        "whiteboard_root": whiteboard.exists(),
        "whiteboard_python": whiteboard_python.exists(),
        "image_adapter": image_script.exists(),
        "tts_adapter": tts_script.exists(),
        "vox_director": (vox_director / "SKILL.md").exists(),
        "runninghub_key": bool(get_runninghub_key(settings)),
        "chatcut_installed": _chatcut_installed(),
    }


def get_runninghub_key(settings: dict[str, Any]) -> str:
    import configparser
    import os

    profile = os.environ.get(
        "RUNNINGHUB_API_PROFILE", settings.get("runninghub", {}).get("api_profile", "member")
    )
    enterprise = str(profile).strip().lower() in {"enterprise", "shared", "enterprise_shared"}
    value = os.environ.get(
        "RUNNINGHUB_ENTERPRISE_API_KEY" if enterprise else "RUNNINGHUB_API_KEY", ""
    ).strip()
    if value:
        return value
    if os.name == "nt":
        try:
            import winreg

            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as key:
                env_name = "RUNNINGHUB_ENTERPRISE_API_KEY" if enterprise else "RUNNINGHUB_API_KEY"
                value, _ = winreg.QueryValueEx(key, env_name)
                if str(value).strip():
                    return str(value).strip()
        except OSError:
            pass
    if enterprise:
        return ""
    config_path = (
        Path(settings["paths"]["whiteboard_root"])
        / "auto-whiteboard/config/config.ini"
    )
    parser = configparser.ConfigParser()
    if config_path.exists():
        parser.read(config_path, encoding="utf-8-sig")
        return parser.get("RunningHub", "api_key", fallback="").strip()
    return ""


def _chatcut_installed() -> bool:
    root = Path.home() / ".codex/plugins/cache/chatcut-inc/chatcut"
    return root.exists() and any(root.iterdir())
