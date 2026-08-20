from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from .assembler import assemble
from .chatcut import create_handoff
from .image_adapter import generate_images_sync
from .planner import create_plan
from .runninghub import generate_videos
from .tts_adapter import generate_voice


def plan_project(
    settings: dict[str, Any], project_name: str, script: Path, force: bool = False
) -> Path:
    project = Path(settings["paths"]["projects_root"]) / project_name
    project.mkdir(parents=True, exist_ok=True)
    local_script = project / "script.txt"
    if force or not local_script.exists() or local_script.read_bytes() != script.read_bytes():
        shutil.copy2(script, local_script)
    plan_path = project / "beats.json"
    if force or not plan_path.exists():
        create_plan(
            project_name,
            local_script,
            plan_path,
            aspect=settings["project"].get("aspect", "9:16"),
            target_beat_seconds=float(settings["project"].get("target_beat_seconds", 9.0)),
            shots_per_beat=int(settings["project"].get("shots_per_beat", 2)),
        )
    return project


def run_pipeline(
    settings: dict[str, Any], project_name: str, script: Path, force: bool = False
) -> dict[str, Any]:
    project = plan_project(settings, project_name, script, force=force)
    if settings.get("tts", {}).get("enabled", True):
        generate_voice(settings, project, force=force)
    generate_images_sync(settings, project, force=force)
    generate_videos(settings, project, force=force)
    report = assemble(settings, project, force=force)
    create_handoff(settings, project)
    return report
