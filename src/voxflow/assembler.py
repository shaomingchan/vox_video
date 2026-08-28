from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .planner import iter_shots
from .util import (
    ffprobe,
    media_duration,
    parse_srt_seconds,
    read_json,
    run,
    srt_duration,
    write_json,
)


def allocate_shot_durations(plan: dict[str, Any], total_duration: float) -> list[dict[str, Any]]:
    beats = plan["beats"]
    weights = [max(1, len(beat["narration"])) for beat in beats]
    total_weight = sum(weights)
    timeline: list[dict[str, Any]] = []
    cursor = 0.0
    for beat, weight in zip(beats, weights):
        beat_duration = total_duration * weight / total_weight
        shots = beat["shots"]
        each = beat_duration / len(shots)
        for shot in shots:
            timeline.append(
                {
                    "shot_id": shot["id"],
                    "beat_id": beat["id"],
                    "start": round(cursor, 3),
                    "duration": round(each, 3),
                    "clip": shot.get("clip"),
                    "keyframe": shot.get("keyframe"),
                }
            )
            cursor += each
    if timeline:
        timeline[-1]["duration"] = round(total_duration - timeline[-1]["start"], 3)
    return timeline


def _subtitle_filter(
    path: Path, font: str, font_size: int = 56, margin_bottom: int = 64,
    width: int = 1080, height: int = 1920, outline: int = 3, shadow: int = 2,
) -> str:
    escaped = str(path.resolve()).replace("\\", "/").replace(":", "\\:").replace("'", "\\'")
    style = (
        f"PlayResX={width},PlayResY={height},"
        f"FontName={font},FontSize={font_size},PrimaryColour=&H00FFFFFF,"
        f"OutlineColour=&H00000000,BorderStyle=1,Outline={outline},Shadow={shadow},"
        f"Alignment=2,MarginV={margin_bottom}"
    )
    return f"subtitles='{escaped}':force_style='{style}'"


def _shot_map(plan: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {shot["id"]: shot for _, shot in iter_shots(plan)}


def _text_safe_keyframe(settings: dict[str, Any], shot: dict[str, Any]) -> bool:
    mode = str(settings["assembly"].get("text_safe_mode", "keyframe")).lower()
    if mode in {"off", "none", "false"}:
        return False
    return bool(shot.get("text_safe", shot.get("title", False)))


def _repaired_clip(repair_dir: Path, shot_id: str) -> Path | None:
    candidate = repair_dir / f"shot-{shot_id}.mp4"
    return candidate if candidate.exists() else None


def _normalized_target(
    normalized_dir: Path, item: dict[str, Any], use_keyframe: bool, repaired: bool = False,
) -> Path:
    suffix = "-repaired" if repaired else ("-keyframe" if use_keyframe else "")
    return normalized_dir / f"shot-{item['shot_id']}{suffix}.mp4"


def _output_dimensions(
    settings: dict[str, Any], timeline: list[dict[str, Any]],
    default_width: int, default_height: int,
) -> tuple[int, int]:
    mode = str(settings["assembly"].get("resolution_mode", "configured")).lower()
    if mode != "source" or not timeline:
        return default_width, default_height
    source = Path(timeline[0].get("clip", ""))
    if not source.exists():
        return default_width, default_height
    probe = ffprobe(source)
    stream = next(
        (item for item in probe.get("streams", []) if item.get("codec_type") == "video"),
        None,
    )
    if not stream:
        return default_width, default_height
    return int(stream["width"]), int(stream["height"])


def _trim_srt(source: Path, target: Path, duration: float) -> None:
    blocks = re.split(r"\r?\n\s*\r?\n", source.read_text(encoding="utf-8-sig").strip())
    kept: list[str] = []
    timing = re.compile(
        r"(?P<start>\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*"
        r"(?P<end>\d{2}:\d{2}:\d{2},\d{3})"
    )

    def format_time(seconds: float) -> str:
        milliseconds = max(0, round(seconds * 1000))
        hours, milliseconds = divmod(milliseconds, 3_600_000)
        minutes, milliseconds = divmod(milliseconds, 60_000)
        secs, milliseconds = divmod(milliseconds, 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{milliseconds:03d}"

    for block in blocks:
        match = timing.search(block)
        if not match:
            continue
        start = parse_srt_seconds(match.group("start"))
        end = parse_srt_seconds(match.group("end"))
        if start >= duration:
            continue
        lines = block.splitlines()
        text_start = next((index + 1 for index, line in enumerate(lines) if "-->" in line), 2)
        text = "\n".join(lines[text_start:]).strip()
        if not text:
            continue
        kept.append(
            f"{len(kept) + 1}\n{format_time(start)} --> {format_time(min(end, duration))}\n{text}"
        )
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("\n\n".join(kept) + ("\n" if kept else ""), encoding="utf-8")


def _ffmpeg_concat_entry(path: Path) -> str:
    normalized = str(path.resolve()).replace("\\", "/")
    escaped = normalized.replace("'", "'\\''")
    return f"file '{escaped}'"


def assemble_preview(
    settings: dict[str, Any], project: Path, limit: int, force: bool = False
) -> dict[str, Any]:
    if limit < 1:
        raise ValueError("Preview limit must be at least 1")
    plan = read_json(project / "beats.json")
    if not plan:
        raise RuntimeError(f"Missing plan: {project / 'beats.json'}")
    audio = read_json(project / "audio/manifest.json", {}) or {}
    voiceover = Path(audio.get("voiceover_path", "")) if audio else None
    subtitles = Path(audio.get("srt_path", "")) if audio else None
    if not voiceover or not voiceover.exists():
        raise RuntimeError("Preview assembly requires the project voiceover")

    full_duration = media_duration(voiceover)
    full_timeline = allocate_shot_durations(plan, full_duration)
    timeline = full_timeline[:limit]
    if len(timeline) < limit:
        raise RuntimeError(f"Project has only {len(timeline)} shots, fewer than requested {limit}")
    if any(not item.get("clip") or not Path(item["clip"]).exists() for item in timeline):
        raise RuntimeError("One or more selected RunningHub clips are missing")
    total_duration = round(timeline[-1]["start"] + timeline[-1]["duration"], 3)

    preview_dir = project / "previews" / f"first-{limit:03d}"
    normalized_dir = preview_dir / "normalized"
    normalized_dir.mkdir(parents=True, exist_ok=True)
    width, height = _output_dimensions(
        settings,
        timeline,
        int(settings["assembly"].get("width", 1920)),
        int(settings["assembly"].get("height", 1080)),
    )
    fps = int(settings["assembly"].get("fps", 24))
    crf = int(settings["assembly"].get("crf", 16))
    shots_by_id = _shot_map(plan)
    video_preset = str(settings["assembly"].get("video_preset", "slow"))
    deflicker_frames = max(2, int(settings["assembly"].get("deflicker_frames", 3)))
    sharpen = float(settings["assembly"].get("sharpen_luma", 0.25))

    preview_voice = preview_dir / "voiceover.wav"
    if force or not preview_voice.exists():
        run(
            [
                "ffmpeg",
                "-y",
                "-i",
                str(voiceover),
                "-t",
                f"{total_duration:.3f}",
                "-c:a",
                "pcm_s16le",
                str(preview_voice),
            ]
        )
    preview_srt = preview_dir / "subtitles.srt"
    if subtitles and subtitles.exists():
        _trim_srt(subtitles, preview_srt, total_duration)

    normalized_files: list[Path] = []
    repaired_dir = preview_dir / "repaired"
    repaired_shot_ids: list[str] = []
    for item in timeline:
        source = Path(item["clip"])
        shot = shots_by_id.get(item["shot_id"], {})
        repaired = _repaired_clip(repaired_dir, item["shot_id"])
        use_keyframe = (
            repaired is None
            and _text_safe_keyframe(settings, shot)
            and Path(shot.get("keyframe", "")).exists()
        )
        if repaired is not None:
            source = repaired
            repaired_shot_ids.append(item["shot_id"])
        elif use_keyframe:
            source = Path(shot["keyframe"])
        target = _normalized_target(normalized_dir, item, use_keyframe, repaired is not None)
        if force or not target.exists():
            if use_keyframe:
                video_filter = (
                    f"scale={width}:{height}:force_original_aspect_ratio=increase:flags=lanczos,"
                    f"crop={width}:{height},"
                    f"zoompan=z='min(zoom+0.0005,1.03)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
                    f"d=1:s={width}x{height}:fps={fps},setsar=1"
                )
                input_args = ["-loop", "1", "-framerate", str(fps), "-i", str(source)]
            else:
                video_filter = (
                    f"fps={fps},deflicker=size={deflicker_frames}:mode=median,"
                    f"scale={width}:{height}:force_original_aspect_ratio=increase:flags=lanczos,"
                    f"crop={width}:{height},unsharp=5:5:{sharpen}:5:5:0,setsar=1"
                )
                input_args = ["-stream_loop", "-1", "-i", str(source)]
            run(
                [
                    "ffmpeg",
                    "-y",
                    *input_args,
                    "-t",
                    f"{item['duration']:.3f}",
                    "-vf",
                    video_filter,
                    "-an",
                    "-c:v",
                    "libx264",
                    "-preset",
                    video_preset,
                    "-crf",
                    str(crf),
                    "-pix_fmt",
                    "yuv420p",
                    "-r",
                    str(fps),
                    "-fps_mode",
                    "cfr",
                    str(target),
                ]
            )
        normalized_files.append(target)

    concat_file = preview_dir / "concat.txt"
    concat_file.write_text(
        "\n".join(_ffmpeg_concat_entry(path) for path in normalized_files),
        encoding="utf-8",
    )
    silent = preview_dir / "silent.mp4"
    run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(concat_file),
            "-fflags",
            "+genpts",
            "-c",
            "copy",
            str(silent),
        ]
    )

    final = preview_dir / "preview.mp4"
    bgm = Path(settings["assembly"].get("bgm", ""))
    command = ["ffmpeg", "-y", "-i", str(silent), "-i", str(preview_voice)]
    has_bgm = bgm.exists()
    if has_bgm:
        command.extend(["-stream_loop", "-1", "-i", str(bgm)])
    filters: list[str] = []
    video_map = "0:v:0"
    if settings["assembly"].get("burn_captions", True) and preview_srt.exists():
        filters.append(
            f"[0:v]{_subtitle_filter(preview_srt, settings['assembly'].get('caption_font', 'Microsoft YaHei'), int(settings['assembly'].get('caption_font_size', 56)), int(settings['assembly'].get('caption_margin_bottom', 64)), width, height, int(settings['assembly'].get('caption_outline', 3)), int(settings['assembly'].get('caption_shadow', 2)))}[v]"
        )
        video_map = "[v]"
    if has_bgm:
        bgm_db = float(settings["assembly"].get("bgm_volume_db", -28))
        target_lufs = float(settings["assembly"].get("voice_target_lufs", -16))
        filters.extend(
            [
                "[1:a]volume=1.0[voice]",
                f"[2:a]volume={bgm_db}dB[music]",
                f"[voice][music]amix=inputs=2:duration=first:dropout_transition=2,"
                f"loudnorm=I={target_lufs}:TP=-1.5:LRA=11[a]",
            ]
        )
        audio_map = "[a]"
    else:
        audio_map = "1:a:0"
    if filters:
        command.extend(["-filter_complex", ";".join(filters)])
    command.extend(
        [
            "-map",
            video_map,
            "-map",
            audio_map,
            "-t",
            f"{total_duration:.3f}",
            "-c:v",
            "libx264",
            "-preset",
            "medium",
            "-crf",
            str(crf),
            "-pix_fmt",
            "yuv420p",
            "-r",
            str(fps),
            "-fps_mode",
            "cfr",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-movflags",
            "+faststart",
            str(final),
        ]
    )
    run(command)
    probe = ffprobe(final)
    video_stream = next(
        stream for stream in probe.get("streams", []) if stream.get("codec_type") == "video"
    )
    report = {
        "preview_video": str(final.resolve()),
        "duration": float(probe["format"]["duration"]),
        "output_width": video_stream.get("width"),
        "output_height": video_stream.get("height"),
        "fps": fps,
        "resolution_mode": settings["assembly"].get("resolution_mode", "configured"),
        "text_safe_shot_ids": [
            item["shot_id"]
            for item in timeline
            if _text_safe_keyframe(settings, shots_by_id.get(item["shot_id"], {}))
        ],
        "repaired_shot_ids": repaired_shot_ids,
        "shot_count": len(timeline),
        "shot_ids": [item["shot_id"] for item in timeline],
        "voiceover": str(preview_voice.resolve()),
        "subtitles": str(preview_srt.resolve()) if preview_srt.exists() else None,
        "timeline": timeline,
    }
    write_json(preview_dir / "composition_report.json", report)
    return report


def assemble(settings: dict[str, Any], project: Path, force: bool = False) -> dict[str, Any]:
    plan = read_json(project / "beats.json")
    if not plan:
        raise RuntimeError(f"Missing plan: {project / 'beats.json'}")
    audio = read_json(project / "audio/manifest.json", {}) or {}
    voiceover = Path(audio.get("voiceover_path", "")) if audio else None
    subtitles = Path(audio.get("srt_path", "")) if audio else None
    if voiceover and voiceover.exists():
        total_duration = media_duration(voiceover)
    else:
        total_duration = sum(float(shot.get("duration", 5)) for _, shot in iter_shots(plan))
    timeline = allocate_shot_durations(plan, total_duration)
    if any(not item.get("clip") or not Path(item["clip"]).exists() for item in timeline):
        raise RuntimeError("One or more RunningHub clips are missing")

    final_dir = project / "final"
    normalized_dir = final_dir / "normalized"
    normalized_dir.mkdir(parents=True, exist_ok=True)
    repaired_dir = final_dir / "repaired"
    width, height = _output_dimensions(
        settings,
        timeline,
        int(settings["assembly"].get("width", 1080)),
        int(settings["assembly"].get("height", 1920)),
    )
    fps = int(settings["assembly"].get("fps", 24))
    crf = int(settings["assembly"].get("crf", 16))
    shots_by_id = _shot_map(plan)
    video_preset = str(settings["assembly"].get("video_preset", "slow"))
    deflicker_frames = max(2, int(settings["assembly"].get("deflicker_frames", 3)))
    sharpen = float(settings["assembly"].get("sharpen_luma", 0.25))
    normalized_files: list[Path] = []
    repaired_shot_ids: list[str] = []
    for item in timeline:
        source = Path(item["clip"])
        shot = shots_by_id.get(item["shot_id"], {})
        repaired = _repaired_clip(repaired_dir, item["shot_id"])
        use_keyframe = (
            repaired is None
            and _text_safe_keyframe(settings, shot)
            and Path(shot.get("keyframe", "")).exists()
        )
        if repaired is not None:
            source = repaired
            repaired_shot_ids.append(item["shot_id"])
        elif use_keyframe:
            source = Path(shot["keyframe"])
        target = _normalized_target(normalized_dir, item, use_keyframe, repaired is not None)
        if force or not target.exists():
            if use_keyframe:
                video_filter = (
                    f"scale={width}:{height}:force_original_aspect_ratio=increase:flags=lanczos,"
                    f"crop={width}:{height},"
                    f"zoompan=z='min(zoom+0.0005,1.03)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
                    f"d=1:s={width}x{height}:fps={fps},setsar=1"
                )
                input_args = ["-loop", "1", "-framerate", str(fps), "-i", str(source)]
            else:
                video_filter = (
                    f"fps={fps},deflicker=size={deflicker_frames}:mode=median,"
                    f"scale={width}:{height}:force_original_aspect_ratio=increase:flags=lanczos,"
                    f"crop={width}:{height},unsharp=5:5:{sharpen}:5:5:0,setsar=1"
                )
                input_args = ["-stream_loop", "-1", "-i", str(source)]
            run(
                [
                    "ffmpeg",
                    "-y",
                    *input_args,
                    "-t",
                    f"{item['duration']:.3f}",
                    "-vf",
                    video_filter,
                    "-an",
                    "-c:v",
                    "libx264",
                    "-preset",
                    video_preset,
                    "-crf",
                    str(crf),
                    "-pix_fmt",
                    "yuv420p",
                    "-r",
                    str(fps),
                    "-fps_mode",
                    "cfr",
                    str(target),
                ]
            )
        normalized_files.append(target)

    concat_file = final_dir / "concat.txt"
    concat_file.write_text(
        "\n".join(_ffmpeg_concat_entry(path) for path in normalized_files),
        encoding="utf-8",
    )
    silent = final_dir / "silent.mp4"
    run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(concat_file),
            "-fflags",
            "+genpts",
            "-c",
            "copy",
            str(silent),
        ]
    )

    final = final_dir / "final_video.mp4"
    command = ["ffmpeg", "-y", "-i", str(silent)]
    voice_index = None
    bgm_index = None
    if voiceover and voiceover.exists():
        voice_index = len([arg for arg in command if arg == "-i"])
        command.extend(["-i", str(voiceover)])
    bgm = Path(settings["assembly"].get("bgm", ""))
    if bgm.exists() and voice_index is not None:
        command.extend(["-stream_loop", "-1", "-i", str(bgm)])
        bgm_index = 2

    filters: list[str] = []
    video_map = "0:v:0"
    if (
        settings["assembly"].get("burn_captions", True)
        and subtitles
        and subtitles.exists()
    ):
        filters.append(
            f"[0:v]{_subtitle_filter(subtitles, settings['assembly'].get('caption_font', 'Microsoft YaHei'), int(settings['assembly'].get('caption_font_size', 56)), int(settings['assembly'].get('caption_margin_bottom', 64)), width, height, int(settings['assembly'].get('caption_outline', 3)), int(settings['assembly'].get('caption_shadow', 2)))}[v]"
        )
        video_map = "[v]"

    audio_map = None
    if voice_index is not None and bgm_index is not None:
        bgm_db = float(settings["assembly"].get("bgm_volume_db", -28))
        target_lufs = float(settings["assembly"].get("voice_target_lufs", -16))
        filters.append(f"[{voice_index}:a]volume=1.0[voice]")
        filters.append(f"[{bgm_index}:a]volume={bgm_db}dB[music]")
        filters.append(
            f"[voice][music]amix=inputs=2:duration=first:dropout_transition=2,"
            f"loudnorm=I={target_lufs}:TP=-1.5:LRA=11[a]"
        )
        audio_map = "[a]"
    elif voice_index is not None:
        audio_map = f"{voice_index}:a:0"

    if filters:
        command.extend(["-filter_complex", ";".join(filters)])
    command.extend(["-map", video_map])
    if audio_map:
        command.extend(["-map", audio_map, "-c:a", "aac", "-b:a", "192k"])
    command.extend(
        [
            "-t",
            f"{total_duration:.3f}",
            "-c:v",
            "libx264",
            "-preset",
            "medium",
            "-crf",
            str(crf),
            "-pix_fmt",
            "yuv420p",
            "-r",
            str(fps),
            "-fps_mode",
            "cfr",
            "-movflags",
            "+faststart",
            str(final),
        ]
    )
    run(command)
    probe = ffprobe(final)
    video_duration = float(probe["format"]["duration"])
    audio_duration = media_duration(voiceover) if voiceover and voiceover.exists() else video_duration
    report = {
        "final_video": str(final.resolve()),
        "duration": video_duration,
        "audio_duration": audio_duration,
        "av_delta_seconds": abs(video_duration - audio_duration),
        "output_width": width,
        "output_height": height,
        "fps": fps,
        "resolution_mode": settings["assembly"].get("resolution_mode", "configured"),
        "text_safe_shot_ids": [
            item["shot_id"]
            for item in timeline
            if _text_safe_keyframe(settings, shots_by_id.get(item["shot_id"], {}))
        ],
        "repaired_shot_ids": repaired_shot_ids,
        "shot_count": len(timeline),
        "subtitle_duration": srt_duration(subtitles) if subtitles and subtitles.exists() else 0,
        "timeline": timeline,
    }
    write_json(final_dir / "composition_report.json", report)
    return report
