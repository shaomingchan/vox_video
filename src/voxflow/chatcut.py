from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

from .assembler import allocate_shot_durations
from .planner import iter_shots
from .util import media_duration, read_json, write_json


def create_handoff(
    settings: dict[str, Any], project: Path, limit: int | None = None
) -> dict[str, Any]:
    plan = read_json(project / "beats.json")
    audio = read_json(project / "audio/manifest.json", {}) or {}
    voiceover = Path(audio.get("voiceover_path", "")) if audio else None
    subtitles = audio.get("srt_path")
    output_dir = project / "final"
    if limit is not None:
        preview_dir = project / "previews" / f"first-{limit:03d}"
        preview_report = read_json(preview_dir / "composition_report.json", {}) or {}
        if not preview_report:
            raise RuntimeError(
                f"Missing preview composition report; run preview --limit {limit} first"
            )
        timeline = preview_report["timeline"]
        voiceover = Path(preview_report["voiceover"])
        subtitles = preview_report.get("subtitles")
        output_dir = preview_dir
    else:
        duration = media_duration(voiceover) if voiceover and voiceover.exists() else sum(
            float(shot.get("duration", 5)) for _, shot in iter_shots(plan)
        )
        timeline = allocate_shot_durations(plan, duration)
    handoff = {
        "project_name": (
            f"{settings['chatcut'].get('project_prefix', 'VoxFlow')} - {plan['project']}"
            + (f" - first {limit} shots" if limit is not None else "")
        ),
        "aspect": plan["aspect"],
        "voiceover": str(voiceover.resolve()) if voiceover and voiceover.exists() else None,
        "subtitles": subtitles,
        "clips": timeline,
        "editing": {
            "cuts": "hard editorial cuts",
            "preserve_on_screen_text": True,
            "caption_style": "clean Chinese captions, bottom-center, 40px bottom margin",
            "bgm": settings["assembly"].get("bgm"),
            "bgm_volume_db": settings["assembly"].get("bgm_volume_db", -28),
            "voice_target_lufs": settings["assembly"].get("voice_target_lufs", -16),
            "mute_source_clip_audio": True,
        },
    }
    write_json(output_dir / "chatcut_handoff.json", handoff)
    prompt = f"""Use the ChatCut plugin to create a new editable project named {handoff['project_name']}.
Import every original clip listed in {output_dir / 'chatcut_handoff.json'}, plus the voiceover and subtitle files.
Build the timeline in the listed order and durations. Keep every source as an editable timeline item; do not upload a pre-flattened local preview as the main edit.
Use hard editorial cuts and preserve collage text readability. Mute every source video clip's audio. Normalize narration to -16 LUFS with a -1.5 dBTP ceiling, set BGM to -28 dB, and place the supplied Chinese captions bottom-center with a 40px bottom margin.
Set the timeline canvas to 1920x1080 at 24 fps. Verify there are no gaps or unintended overlaps. Keep the project open for review; do not export.
"""
    (output_dir / "chatcut_prompt.txt").write_text(prompt, encoding="utf-8")
    return handoff


def launch_chatcut(
    settings: dict[str, Any], project: Path, limit: int | None = None
) -> None:
    create_handoff(settings, project, limit=limit)
    prompt_path = (
        project / "previews" / f"first-{limit:03d}" / "chatcut_prompt.txt"
        if limit is not None
        else project / "final/chatcut_prompt.txt"
    )
    codex_js = Path.home() / "AppData/Roaming/npm/node_modules/@openai/codex/bin/codex.js"
    node = shutil.which("node")
    if not node or not codex_js.exists():
        raise RuntimeError("Codex Node CLI entry point was not found")
    command = [
        node,
        str(codex_js),
        "exec",
        "--skip-git-repo-check",
        "--dangerously-bypass-approvals-and-sandbox",
        "--cd",
        str(project.resolve()),
        "-",
    ]
    result = subprocess.run(
        command,
        input=prompt_path.read_text(encoding="utf-8"),
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        raise RuntimeError("ChatCut Codex handoff failed")
