from __future__ import annotations

import json
import hashlib
import mimetypes
import os
import random
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from .config import get_runninghub_key
from .planner import iter_shots
from .util import read_json, sha256_file, sha256_text, write_json


API_ROOT = "https://www.runninghub.cn/openapi/v2"
ASPECT_VALUES = {
    "9:16": "9:16 (Portrait Widescreen)",
    "16:9": "16:9 (Widescreen)",
    "1:1": "1:1 (Square)",
    "3:4": "3:4 (Portrait Standard)",
    "4:3": "4:3 (Standard)",
}


class RunningHubError(RuntimeError):
    pass


def effective_instance_type(config: dict[str, Any]) -> str:
    """Use Plus automatically for an explicitly selected enterprise profile."""
    profile = os.environ.get("RUNNINGHUB_API_PROFILE", config.get("api_profile", "member"))
    if str(profile).strip().lower() in {"enterprise", "shared", "enterprise_shared"}:
        return str(config.get("enterprise_instance_type", "plus"))
    return str(config.get("instance_type", "default"))


def effective_concurrency(config: dict[str, Any]) -> int:
    """Keep the member safety cap while allowing the enterprise shared limit."""
    profile = os.environ.get("RUNNINGHUB_API_PROFILE", config.get("api_profile", "member"))
    enterprise = str(profile).strip().lower() in {"enterprise", "shared", "enterprise_shared"}
    configured = int(
        config.get("enterprise_concurrency" if enterprise else "concurrency", 100 if enterprise else 3)
    )
    return min(100 if enterprise else 3, max(1, configured))


def _json_request(url: str, key: str, payload: dict[str, Any]) -> dict[str, Any]:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "User-Agent": "voxflow/0.1",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:1000]
        raise RunningHubError(f"RunningHub HTTP {exc.code}: {detail}") from exc


def upload_file(path: Path, key: str) -> str:
    boundary = f"----voxflow-{uuid.uuid4().hex}"
    mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    prefix = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="{path.name}"\r\n'
        f"Content-Type: {mime}\r\n\r\n"
    ).encode("utf-8")
    body = prefix + path.read_bytes() + f"\r\n--{boundary}--\r\n".encode("utf-8")
    request = urllib.request.Request(
        f"{API_ROOT}/media/upload/binary",
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "User-Agent": "voxflow/0.1",
        },
    )
    with urllib.request.urlopen(request, timeout=180) as response:
        result = json.loads(response.read().decode("utf-8"))
    if result.get("code") != 0 or not result.get("data", {}).get("fileName"):
        raise RunningHubError(f"Upload failed: {result.get('message') or result.get('code')}")
    return result["data"]["fileName"]


def build_payload(
    config: dict[str, Any], image_name: str, prompt: str, aspect: str, seed: int
) -> dict[str, Any]:
    aspect_value = ASPECT_VALUES.get(aspect)
    if not aspect_value:
        raise ValueError(f"Unsupported RunningHub aspect: {aspect}")
    duration = "5"
    node_info = [
        {"nodeId": node, "fieldName": "image", "fieldValue": image_name}
        for node in ("97", "101", "132")
    ]
    node_info.extend(
        [
            {"nodeId": "83", "fieldName": "text", "fieldValue": prompt},
            {"nodeId": "84", "fieldName": "value", "fieldValue": duration},
            {"nodeId": "105", "fieldName": "aspect_ratio", "fieldValue": aspect_value},
            {"nodeId": "297", "fieldName": "aspect_ratio", "fieldValue": aspect_value},
            {"nodeId": "243", "fieldName": "noise_seed", "fieldValue": str(seed)},
            {"nodeId": "300", "fieldName": "noise_seed", "fieldValue": str(seed)},
        ]
    )
    payload = {
        "addMetadata": True,
        "nodeInfoList": node_info,
        "usePersonalQueue": bool(config.get("use_personal_queue", False)),
    }
    # Lite is selected by RunningHub's scheduler; its API contract omits
    # instanceType, while Standard/Plus require default/plus respectively.
    instance_type = effective_instance_type(config).strip().lower()
    if instance_type not in {"", "lite", "auto"}:
        payload["instanceType"] = instance_type
    return payload


def _wait_for_task(task_id: str, key: str, config: dict[str, Any]) -> dict[str, Any]:
    started = time.monotonic()
    poll_seconds = max(3, int(config.get("poll_seconds", 10)))
    timeout = max(60, int(config.get("timeout_seconds", 1800)))
    last_status = ""
    query_errors = 0
    while time.monotonic() - started < timeout:
        try:
            result = _json_request(f"{API_ROOT}/query", key, {"taskId": task_id})
            query_errors = 0
        except Exception as exc:
            query_errors += 1
            if query_errors >= 5:
                raise RunningHubError(
                    f"Task {task_id} status could not be queried after {query_errors} attempts: {exc}"
                ) from exc
            time.sleep(poll_seconds)
            continue
        status = result.get("status", "UNKNOWN")
        if status != last_status:
            print(f"[runninghub] {task_id}: {status}", flush=True)
            last_status = status
        if status == "SUCCESS":
            return result
        if status == "FAILED":
            failed = result.get("failedReason") or result.get("errorMessage") or "unknown failure"
            raise RunningHubError(f"Task {task_id} failed: {failed}")
        time.sleep(poll_seconds)
    raise TimeoutError(f"RunningHub task timed out: {task_id}")


def _download_result(result: dict[str, Any], target: Path, output_node_id: str) -> None:
    candidates = [item for item in result.get("results") or [] if item.get("url")]
    preferred = [item for item in candidates if str(item.get("nodeId")) == output_node_id]
    item = (preferred or candidates or [None])[0]
    if not item:
        raise RunningHubError("Task succeeded without a downloadable result")
    target.parent.mkdir(parents=True, exist_ok=True)
    url = urllib.parse.quote(item["url"], safe=":/?&=%#+;,[]@!$'()*")
    last_error: Exception | None = None
    for attempt in range(1, 4):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "voxflow/0.1"})
            with urllib.request.urlopen(request, timeout=300) as response, target.open("wb") as handle:
                while chunk := response.read(1024 * 1024):
                    handle.write(chunk)
            last_error = None
            break
        except Exception as exc:
            last_error = exc
            time.sleep(attempt * 2)
    if last_error:
        raise RunningHubError(f"Could not download successful task result: {last_error}")
    if target.stat().st_size < 1024:
        raise RunningHubError(f"Downloaded clip is too small: {target}")


def _generate_one(
    shot: dict[str, Any], aspect: str, output_dir: Path, key: str, config: dict[str, Any]
) -> dict[str, Any]:
    image_path = Path(shot["keyframe"])
    target = output_dir / f"shot-{shot['id']}.mp4"
    seed = int(sha256_text(shot["video_prompt"] + sha256_file(image_path))[:12], 16) % 10**12
    attempts = max(1, int(config.get("retries", 2)))
    last_error: Exception | None = None
    task_id: str | None = None
    for attempt in range(1, attempts + 1):
        try:
            uploaded = upload_file(image_path, key)
            payload = build_payload(config, uploaded, shot["video_prompt"], aspect, seed)
            response = _json_request(
                f"{API_ROOT}/run/workflow/{config['workflow_id']}", key, payload
            )
            task_id = response.get("taskId")
            if not task_id:
                raise RunningHubError(f"Submit failed: {response.get('errorMessage') or response}")
            print(f"[runninghub] shot {shot['id']} submitted as {task_id}", flush=True)
            break
        except RunningHubError as exc:
            last_error = exc
            if attempt < attempts:
                time.sleep(3 * attempt + random.random())
    if not task_id:
        raise RunningHubError(f"Shot {shot['id']} failed before submission: {last_error}")

    # Once RunningHub returns a task ID, never submit a replacement automatically.
    # Polling, provider failure and result-download errors all retain that billable task ID.
    try:
        result = _wait_for_task(task_id, key, config)
        _download_result(result, target, str(config.get("output_node_id", "386")))
    except Exception as exc:
        raise RunningHubError(f"Shot {shot['id']} task {task_id} needs attention: {exc}") from exc
    return {
        "shot_id": shot["id"],
        "path": str(target.resolve()),
        "task_id": task_id,
        "sha256": sha256_file(target),
        "usage": result.get("usage") or {},
    }


def _select_shots(
    plan: dict[str, Any], shot_ids: list[str] | None, limit: int | None
) -> list[dict[str, Any]]:
    shots = [shot for _, shot in iter_shots(plan)]
    if shot_ids:
        requested = list(dict.fromkeys(str(value).zfill(3) for value in shot_ids))
        by_id = {str(shot["id"]): shot for shot in shots}
        missing = [shot_id for shot_id in requested if shot_id not in by_id]
        if missing:
            raise ValueError(f"Unknown shot IDs: {', '.join(missing)}")
        shots = [by_id[shot_id] for shot_id in requested]
    if limit is not None:
        if limit < 1:
            raise ValueError("Video limit must be at least 1")
        shots = shots[:limit]
    return shots


def _generate_videos_unlocked(
    settings: dict[str, Any],
    project: Path,
    force: bool = False,
    shot_ids: list[str] | None = None,
    limit: int | None = None,
    allow_large_batch: bool = False,
) -> list[dict[str, Any]]:
    plan_path = project / "beats.json"
    plan = read_json(plan_path)
    if not plan:
        raise RuntimeError(f"Missing plan: {plan_path}")
    key = get_runninghub_key(settings)
    if not key:
        raise RuntimeError("RUNNINGHUB_API_KEY is not configured")
    output_dir = project / "clips"
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = project / "video_manifest.json"
    old = read_json(manifest_path, {}) or {}
    old_items = {item["shot_id"]: item for item in old.get("items", [])}
    selected = _select_shots(plan, shot_ids, limit)
    selected_ids = {str(shot["id"]) for shot in selected}
    complete: dict[str, dict[str, Any]] = dict(old_items)
    pending: list[dict[str, Any]] = []
    fingerprints: dict[str, str] = {}
    for shot in selected:
        image = Path(shot.get("keyframe", ""))
        if not image.exists():
            raise RuntimeError(f"Missing keyframe for shot {shot['id']}")
        target = output_dir / f"shot-{shot['id']}.mp4"
        fingerprint = sha256_text(
            f"{settings['runninghub']['workflow_id']}\n{plan['aspect']}\n{shot['video_prompt']}\n{sha256_file(image)}"
        )
        fingerprints[shot["id"]] = fingerprint
        cached = old_items.get(shot["id"])
        if (
            not force
            and cached
            and cached.get("fingerprint") == fingerprint
            and target.exists()
            and target.stat().st_size > 1024
        ):
            shot["clip"] = str(target.resolve())
            complete[str(shot["id"])] = cached
        else:
            pending.append(shot)

    max_unconfirmed = max(1, int(settings["runninghub"].get("max_unconfirmed_batch", 20)))
    if len(pending) > max_unconfirmed and not allow_large_batch:
        raise RuntimeError(
            "RunningHub paid-batch safety stop: "
            f"{len(pending)} clips are pending, above the unconfirmed limit of {max_unconfirmed}. "
            "Use an explicit --limit/--shot-id selection, or --all for an intentional full run."
        )

    if pending:
        max_workers = effective_concurrency(settings["runninghub"])
        profile = os.environ.get(
            "RUNNINGHUB_API_PROFILE", settings["runninghub"].get("api_profile", "member")
        )
        instance = effective_instance_type(settings["runninghub"])
        print(
            f"[runninghub] generating {len(pending)} clips "
            f"with profile={profile}, instance={instance}, concurrency={max_workers}"
        )
        lock = threading.Lock()
        failures: list[str] = []
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            futures = {
                pool.submit(
                    _generate_one,
                    shot,
                    plan["aspect"],
                    output_dir,
                    key,
                    settings["runninghub"],
                ): shot
                for shot in pending
            }
            for future in as_completed(futures):
                shot = futures[future]
                try:
                    item = future.result()
                    item["fingerprint"] = fingerprints[shot["id"]]
                    shot["clip"] = item["path"]
                    with lock:
                        complete[str(shot["id"])] = item
                        write_json(
                            manifest_path,
                            {
                                "concurrency": max_workers,
                                "items": sorted(
                                    complete.values(), key=lambda value: value["shot_id"]
                                ),
                            },
                        )
                        write_json(plan_path, plan)
                except Exception as exc:
                    failures.append(str(exc))
        if failures:
            raise RunningHubError("; ".join(failures))

    all_complete = sorted(complete.values(), key=lambda item: item["shot_id"])
    write_json(
        manifest_path,
        {"concurrency": effective_concurrency(settings["runninghub"]), "items": all_complete},
    )
    write_json(plan_path, plan)
    return [complete[shot_id] for shot_id in sorted(selected_ids) if shot_id in complete]


def generate_videos(
    settings: dict[str, Any],
    project: Path,
    force: bool = False,
    shot_ids: list[str] | None = None,
    limit: int | None = None,
    allow_large_batch: bool = False,
) -> list[dict[str, Any]]:
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
        handle = kernel32.CreateMutexW(None, False, f"Local\\VoxFlowVideos-{lock_id}")
        if not handle:
            raise OSError(ctypes.get_last_error(), "CreateMutexW failed")
        if ctypes.get_last_error() == 183:
            kernel32.CloseHandle(handle)
            raise RuntimeError(f"Video generation is already running for this project: {project}")
        try:
            return _generate_videos_unlocked(
                settings,
                project,
                force=force,
                shot_ids=shot_ids,
                limit=limit,
                allow_large_batch=allow_large_batch,
            )
        finally:
            kernel32.ReleaseMutex(handle)
            kernel32.CloseHandle(handle)

    lock_path = project / ".video-generation.lock"
    lock_handle = lock_path.open("a+b")
    try:
        import fcntl

        try:
            fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            raise RuntimeError(
                f"Video generation is already running for this project: {lock_path}"
            ) from exc
        return _generate_videos_unlocked(
            settings,
            project,
            force=force,
            shot_ids=shot_ids,
            limit=limit,
            allow_large_batch=allow_large_batch,
        )
    finally:
        lock_handle.close()
