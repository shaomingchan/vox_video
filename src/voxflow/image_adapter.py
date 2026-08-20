from __future__ import annotations

import asyncio
import hashlib
import importlib.util
import os
import shutil
import sys
from pathlib import Path
from typing import Any

from PIL import Image, ImageFilter, ImageOps

from .planner import iter_shots
from .util import read_json, sha256_file, sha256_text, write_json


def _load_whiteboard_module(settings: dict[str, Any]):
    script = (
        Path(settings["paths"]["whiteboard_root"])
        / "skills/whiteboard-video-workflow/scripts/generate-image.py"
    )
    script_dir = str(script.parent)
    if script_dir not in sys.path:
        sys.path.insert(0, script_dir)
    spec = importlib.util.spec_from_file_location("voxflow_whiteboard_image", script)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load whiteboard image adapter: {script}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.load_env()
    return module


def _normalize_aspect(source: Path, target: Path, aspect: str) -> None:
    """Normalize whiteboard's landscape output for the requested film canvas."""
    if aspect == "16:9":
        shutil.copy2(source, target)
        return
    if aspect == "9:16":
        ratio = 9 / 16
    elif aspect == "1:1":
        ratio = 1
    elif aspect == "3:4":
        ratio = 3 / 4
    elif aspect == "4:3":
        ratio = 4 / 3
    else:
        raise ValueError(f"Unsupported output aspect: {aspect}")

    with Image.open(source).convert("RGB") as image:
        width, height = image.size
        target_width = max(1, round(height * ratio))
        if target_width <= width:
            left = (width - target_width) // 2
            normalized = image.crop((left, 0, left + target_width, height))
        else:
            target_height = max(1, round(width / ratio))
            top = max(0, (height - target_height) // 2)
            normalized = image.crop((0, top, width, top + target_height))
        normalized = ImageOps.fit(normalized, (1080, round(1080 / ratio)), method=Image.Resampling.LANCZOS)
        normalized.save(target, format="PNG", optimize=True)


async def generate_images(
    settings: dict[str, Any], project: Path, force: bool = False
) -> list[dict[str, Any]]:
    plan_path = project / "beats.json"
    plan = read_json(plan_path)
    if not plan:
        raise RuntimeError(f"Missing plan: {plan_path}")
    output_dir = project / "images"
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = project / "image_manifest.json"
    old_manifest = read_json(manifest_path, {}) or {}
    old_items = {item["shot_id"]: item for item in old_manifest.get("items", [])}

    provider = settings["image"].get("provider", "apimart_image2")
    os.environ["IMAGE_PROVIDER"] = provider
    module = _load_whiteboard_module(settings)
    concurrency = max(1, int(settings["image"].get("concurrency", 4)))

    pending: list[tuple[dict[str, Any], Path, str]] = []
    complete: list[dict[str, Any]] = []
    for _, shot in iter_shots(plan):
        target = output_dir / f"shot-{shot['id']}.png"
        fingerprint = sha256_text(f"{provider}\n{plan['aspect']}\n{shot['image_prompt']}")
        cached = old_items.get(shot["id"])
        if (
            not force
            and cached
            and cached.get("fingerprint") == fingerprint
            and target.exists()
            and target.stat().st_size > 1024
        ):
            shot["keyframe"] = str(target.resolve())
            complete.append(cached)
        else:
            pending.append((shot, target, fingerprint))

    # A cache-format or fingerprint regression must not silently turn a resume
    # into a large paid batch. Intentional bulk regeneration requires --force.
    if old_items and not force:
        safety_limit = max(10, len(old_items) // 4)
        if len(pending) > safety_limit:
            raise RuntimeError(
                "Image cache safety stop: "
                f"{len(pending)} of {len(old_items)} cached shots would be regenerated. "
                "Inspect manifest fingerprints first, or rerun with --force if this is intentional."
            )

    if pending:
        # Isolate provider scratch files by prompt batch so the whiteboard adapter's
        # index-based filenames cannot accidentally reuse an older prompt's image.
        batch_fingerprint = sha256_text(
            "\n".join(shot["image_prompt"] for shot, _, _ in pending)
        )[:16]
        scratch = output_dir / ".provider" / batch_fingerprint
        scratch.mkdir(parents=True, exist_ok=True)
        # APIMart image2 supports the requested project ratio directly. Generate native
        # portrait frames for 9:16 projects instead of generating landscape art and
        # center-cropping important composition at the next step.
        source_aspect = plan["aspect"]
        tasks = [
            {
                "prompt": shot["image_prompt"],
                "aspectRatio": source_aspect,
                "outputDir": str(scratch),
                "index": index,
                "total": len(pending),
            }
            for index, (shot, _, _) in enumerate(pending)
        ]
        results = await module.run_batch(tasks, concurrency)
        failures: list[str] = []
        for (shot, target, fingerprint), result in zip(pending, results):
            if not isinstance(result, str):
                failures.append(f"shot {shot['id']}: {result}")
                continue
            source = Path(result)
            if not source.exists() or source.stat().st_size < 1024:
                failures.append(f"shot {shot['id']}: provider output is missing")
                continue
            _normalize_aspect(source, target, plan["aspect"])
            shot["keyframe"] = str(target.resolve())
            complete.append(
                {
                    "shot_id": shot["id"],
                    "path": str(target.resolve()),
                    "fingerprint": fingerprint,
                    "sha256": sha256_file(target),
                    "provider": provider,
                }
            )
        if failures:
            complete.sort(key=lambda item: item["shot_id"])
            write_json(manifest_path, {"provider": provider, "items": complete})
            write_json(plan_path, plan)
            raise RuntimeError("Image generation failed: " + "; ".join(failures))

    complete.sort(key=lambda item: item["shot_id"])
    write_json(manifest_path, {"provider": provider, "items": complete})
    write_json(plan_path, plan)
    return complete


def generate_images_sync(settings: dict[str, Any], project: Path, force: bool = False):
    lock_id = hashlib.sha256(str(project.resolve()).encode("utf-8")).hexdigest()[:24]
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CreateMutexW.argtypes = (ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR)
        kernel32.CreateMutexW.restype = wintypes.HANDLE
        kernel32.ReleaseMutex.argtypes = (wintypes.HANDLE,)
        kernel32.ReleaseMutex.restype = wintypes.BOOL
        kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
        kernel32.CloseHandle.restype = wintypes.BOOL
        handle = kernel32.CreateMutexW(None, False, f"Local\\VoxFlowImages-{lock_id}")
        if not handle:
            raise OSError(ctypes.get_last_error(), "CreateMutexW failed")
        already_exists = ctypes.get_last_error() == 183
        if already_exists:
            kernel32.CloseHandle(handle)
            raise RuntimeError(f"Image generation is already running for this project: {project}")
        try:
            return asyncio.run(generate_images(settings, project, force=force))
        finally:
            kernel32.ReleaseMutex(handle)
            kernel32.CloseHandle(handle)

    lock_path = project / ".image-generation.lock"
    lock_handle = lock_path.open("a+b")
    try:
        import fcntl

        try:
            fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            raise RuntimeError(
                f"Image generation is already running for this project: {lock_path}"
            ) from exc
        return asyncio.run(generate_images(settings, project, force=force))
    finally:
        lock_handle.close()
