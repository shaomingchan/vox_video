from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from .util import media_duration, read_json, sha256_text, write_json


def generate_voice(
    settings: dict[str, Any], project: Path, force: bool = False
) -> dict[str, Any]:
    plan = read_json(project / "beats.json")
    if not plan:
        raise RuntimeError(f"Missing plan: {project / 'beats.json'}")
    audio_dir = project / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)
    sentences_path = audio_dir / "sentences.json"
    sentences = [
        {
            "text": beat["narration"],
            "original_text": beat["narration"],
            "subtitle_text": beat["narration"],
            "tts_text": beat["narration"],
        }
        for beat in plan["beats"]
    ]
    write_json(sentences_path, sentences)
    script_path = Path(plan["script_path"])
    fingerprint = sha256_text(
        json.dumps(sentences, ensure_ascii=False) + str(settings["tts"].get("concurrency", 1))
    )
    manifest_path = audio_dir / "manifest.json"
    cached = read_json(manifest_path, {}) or {}
    cached_audio = Path(cached.get("voiceover_path", ""))
    cached_srt = Path(cached.get("srt_path", ""))
    if (
        not force
        and cached.get("fingerprint") == fingerprint
        and cached_audio.exists()
        and cached_srt.exists()
    ):
        return cached

    whiteboard = Path(settings["paths"]["whiteboard_root"])
    python = whiteboard / ".venv/Scripts/python.exe"
    if not python.exists():
        python = Path("python")
    script = whiteboard / "auto-whiteboard/scripts/generate_voiceover.py"
    config = whiteboard / "auto-whiteboard/config/config.ini"
    command = [
        str(python),
        str(script),
        "--sentences",
        str(sentences_path.resolve()),
        "--output-dir",
        str(audio_dir.resolve()),
        "--config",
        str(config.resolve()),
        "--source-text",
        str(script_path.resolve()),
        "--concurrency",
        str(settings["tts"].get("concurrency", 1)),
    ]
    if force:
        command.append("--force-tts")
    result = subprocess.run(
        command,
        cwd=str(whiteboard / "auto-whiteboard"),
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode != 0:
        detail = "\n".join((result.stderr or result.stdout).splitlines()[-20:])
        raise RuntimeError(f"Whiteboard TTS failed:\n{detail}")
    result_lines = [line for line in result.stdout.splitlines() if line.startswith("RESULT_JSON=")]
    if not result_lines:
        raise RuntimeError("Whiteboard TTS completed without RESULT_JSON")
    payload = json.loads(result_lines[-1].split("=", 1)[1])
    voiceover = Path(payload["voiceover_path"])
    subtitles = Path(payload["srt_path"])
    manifest = {
        **payload,
        "voiceover_path": str(voiceover.resolve()),
        "srt_path": str(subtitles.resolve()),
        "duration": media_duration(voiceover),
        "fingerprint": fingerprint,
    }
    write_json(manifest_path, manifest)
    return manifest
