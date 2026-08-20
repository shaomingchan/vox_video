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
    # 只处理 vox_director_root 和 projects_root
    for key in ("vox_director_root", "projects_root"):
        if key in paths and paths[key]:
            paths[key] = _resolve(base, paths[key])
        else:
            paths[key] = ""
    assembly = data.setdefault("assembly", {})
    if assembly.get("bgm"):
        assembly["bgm"] = _resolve(base, assembly["bgm"])
    data["_config_path"] = str(config_path)
    return data


def doctor(settings: dict[str, Any]) -> dict[str, Any]:
    vox_director_root = settings["paths"].get("vox_director_root", "")
    vox_director = Path(vox_director_root) if vox_director_root else None
    
    return {
        "ffmpeg": bool(shutil.which("ffmpeg")),
        "ffprobe": bool(shutil.which("ffprobe")),
        "image_adapter": True,  # 内置适配器始终可用
        "tts_adapter": True,    # 内置适配器始终可用
        "vox_director": (vox_director / "SKILL.md").exists() if vox_director else False,
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
    # 不再从 whiteboard config.ini 读取
    return ""


def _chatcut_installed() -> bool:
    root = Path.home() / ".codex/plugins/cache/chatcut-inc/chatcut"
    return root.exists() and any(root.iterdir())
