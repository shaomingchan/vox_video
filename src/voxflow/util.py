from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(value, ensure_ascii=False, indent=2)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", delete=False, dir=path.parent, suffix=".tmp"
    ) as handle:
        handle.write(payload)
        temp_name = handle.name
    os.replace(temp_name, path)


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run(command: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=str(cwd) if cwd else None,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )


def ffprobe(path: Path) -> dict[str, Any]:
    result = run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration,size,bit_rate",
            "-show_entries",
            "stream=codec_name,codec_type,width,height,r_frame_rate",
            "-of",
            "json",
            str(path),
        ]
    )
    return json.loads(result.stdout)


def media_duration(path: Path) -> float:
    return float(ffprobe(path).get("format", {}).get("duration") or 0)


SRT_TIME = re.compile(
    r"(?P<h>\d{2}):(?P<m>\d{2}):(?P<s>\d{2}),(?P<ms>\d{3})"
)


def parse_srt_seconds(value: str) -> float:
    match = SRT_TIME.fullmatch(value.strip())
    if not match:
        raise ValueError(f"Invalid SRT time: {value}")
    return (
        int(match.group("h")) * 3600
        + int(match.group("m")) * 60
        + int(match.group("s"))
        + int(match.group("ms")) / 1000
    )


def srt_duration(path: Path) -> float:
    if not path.exists():
        return 0.0
    ends = re.findall(r"-->\s*(\d{2}:\d{2}:\d{2},\d{3})", path.read_text(encoding="utf-8-sig"))
    return max((parse_srt_seconds(value) for value in ends), default=0.0)


def project_dir(settings: dict[str, Any], name: str) -> Path:
    return Path(settings["paths"]["projects_root"]) / name
