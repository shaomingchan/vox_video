from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .assembler import assemble, assemble_preview
from .chatcut import create_handoff, launch_chatcut
from .config import doctor, load_config
from .estimate import estimate_costs, format_estimate
from .image_adapter import generate_images_sync
from .pipeline import plan_project, run_pipeline
from .runninghub import generate_videos
from .tts_adapter import generate_voice


def _project(settings, name: str) -> Path:
    return Path(settings["paths"]["projects_root"]) / name


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="voxflow")
    parser.add_argument("--config", default="config.toml")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("doctor")
    plan = sub.add_parser("plan")
    plan.add_argument("--project", required=True)
    plan.add_argument("--script", required=True, type=Path)
    plan.add_argument("--force", action="store_true")

    for name in ("images", "voice", "assemble"):
        item = sub.add_parser(name)
        item.add_argument("--project", required=True)
        item.add_argument("--force", action="store_true")

    videos = sub.add_parser("videos")
    videos.add_argument("--project", required=True)
    videos.add_argument("--force", action="store_true")
    videos.add_argument("--limit", type=int)
    videos.add_argument("--shot-id", action="append", dest="shot_ids")
    videos.add_argument("--all", action="store_true")

    preview = sub.add_parser("preview")
    preview.add_argument("--project", required=True)
    preview.add_argument("--limit", type=int, required=True)
    preview.add_argument("--force", action="store_true")

    run = sub.add_parser("run")
    run.add_argument("--project", required=True)
    run.add_argument("--script", required=True, type=Path)
    run.add_argument("--force", action="store_true")
    run.add_argument("--dry-run", action="store_true")

    chatcut = sub.add_parser("chatcut")
    chatcut.add_argument("--project", required=True)
    chatcut.add_argument("--launch", action="store_true")
    chatcut.add_argument("--limit", type=int)

    estimate = sub.add_parser("estimate")
    estimate.add_argument("--script", required=True, type=Path)
    estimate.add_argument("--project", help="项目名称（可选）")

    args = parser.parse_args(argv)
    settings = load_config(args.config)
    try:
        if args.command == "doctor":
            result = doctor(settings)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0 if all(result.values()) else 1
        if args.command == "estimate":
            script_text = args.script.read_text(encoding="utf-8-sig").strip()
            if not script_text:
                print(f"错误：脚本文件为空 {args.script}", file=sys.stderr)
                return 1
            estimate = estimate_costs(script_text, settings)
            print(format_estimate(estimate))
            return 0
        if args.command == "plan":
            project = plan_project(settings, args.project, args.script, force=args.force)
            print(project / "beats.json")
            return 0
        if args.command == "run":
            project = plan_project(settings, args.project, args.script, force=args.force)
            if args.dry_run:
                print(project / "beats.json")
                return 0
            report = run_pipeline(settings, args.project, args.script, force=args.force)
            print(json.dumps(report, ensure_ascii=False, indent=2))
            return 0
        project = _project(settings, args.project)
        if args.command == "images":
            result = generate_images_sync(settings, project, force=args.force)
        elif args.command == "videos":
            if args.all and (args.limit is not None or args.shot_ids):
                parser.error("--all cannot be combined with --limit or --shot-id")
            result = generate_videos(
                settings,
                project,
                force=args.force,
                shot_ids=args.shot_ids,
                limit=args.limit,
                allow_large_batch=args.all,
            )
        elif args.command == "voice":
            result = generate_voice(settings, project, force=args.force)
        elif args.command == "assemble":
            result = assemble(settings, project, force=args.force)
        elif args.command == "preview":
            result = assemble_preview(settings, project, limit=args.limit, force=args.force)
        elif args.command == "chatcut":
            result = create_handoff(settings, project, limit=args.limit)
            if args.launch:
                launch_chatcut(settings, project, limit=args.limit)
        else:
            parser.error("unknown command")
            return 2
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
