from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .util import sha256_text, write_json


CAMERA_MOVES = ("push_in", "pan_right", "parallax", "pull_out", "tilt_up", "static")
H3_CAMERA_INSTRUCTIONS = {
    "push_in": "The camera pushes in with small amplitude at slow speed toward the central paper subject.",
    "pan_right": "The camera pans right with small amplitude at slow speed across the layered composition.",
    "parallax": (
        "The camera trucks right with small amplitude at slow speed, creating gentle parallax "
        "between foreground, middle-ground and background paper layers."
    ),
    "pull_out": "The camera pulls out with small amplitude at slow speed to reveal the full paper tableau.",
    "tilt_up": "The camera tilts up with small amplitude at slow speed through the stacked paper layers.",
    "static": "The camera holds a static shot while only the specified paper elements move.",
}
BACKGROUNDS = (
    "warm newsprint cream with signal red",
    "federal blue with off-white paper",
    "mustard yellow with charcoal ink",
    "deep forest green with coral accents",
    "brick red with pale cyan scraps",
    "ink black with electric yellow paper",
)
ELEMENT_MOTIONS = (
    "headline settles like pasted paper; arrows draw on; small clippings drift in opposite directions",
    "diagram lines reveal left to right; labels snap into place; halftone dots pulse once",
    "foreground cut-out slides a few pixels; background layers separate in parallax; tape corners flutter",
    "chart bars rise sequentially; one paper marker circles the key fact; newspaper scraps shift subtly",
    "map route draws forward; location pins pop in; the main cut-out remains locked and readable",
    "all motion resolves; loose scraps settle; the final headline holds perfectly still",
)

STYLE_BLOCK = (
    "Editorial documentary paper collage, assembled from clearly separated torn-paper layers, "
    "scissor-cut printed imagery, tape, newsprint, halftone ink, registration marks and tactile paper shadows. "
    "Bold flat colors, strong information hierarchy, asymmetric magazine composition, visible print grain. "
    "Two-dimensional physical collage, not CGI, not glossy 3D, not a website or presentation slide."
)


def split_sentences(text: str) -> list[str]:
    normalized = re.sub(r"\s+", "", text.strip())
    if not normalized:
        return []
    parts = re.findall(r"[^。！？!?；;]+[。！？!?；;]?", normalized)
    return [part.strip() for part in parts if part.strip()]


def estimate_seconds(text: str) -> float:
    chinese = len(re.findall(r"[\u3400-\u9fff]", text))
    latin_words = len(re.findall(r"[A-Za-z0-9]+", text))
    return max(1.4, chinese / 4.2 + latin_words / 2.5)


def group_sentences(sentences: list[str], target_seconds: float) -> list[str]:
    groups: list[str] = []
    current: list[str] = []
    current_seconds = 0.0
    for sentence in sentences:
        seconds = estimate_seconds(sentence)
        if current and current_seconds + seconds > target_seconds * 1.2:
            groups.append("".join(current))
            current = []
            current_seconds = 0.0
        current.append(sentence)
        current_seconds += seconds
    if current:
        groups.append("".join(current))
    return groups


def title_from_text(text: str, limit: int = 10) -> str:
    phrase = re.split(r"[，。！？!?；;：:\"“”‘’、]|但是|而是|因为|所以|却", text, maxsplit=1)[0]
    clean = re.sub(r"\s+", "", phrase)
    return clean[:limit] or "关键一幕"


def image_prompt(
    narration: str,
    title: str,
    background: str,
    detail: bool,
    aspect: str,
    include_text: bool = True,
) -> str:
    orientation = {
        "16:9": "Landscape",
        "9:16": "Portrait",
        "1:1": "Square",
        "3:4": "Portrait",
        "4:3": "Landscape",
    }.get(aspect, "")
    if detail:
        headline = "No typography in this detail shot; leave clean negative space for later captions."
        composition = "A close editorial cut-in that visualizes one concrete object, relationship, map, chart or mechanism from the narration."
    else:
        headline = (
            f'Add one short, exact Chinese headline on a torn paper banner: "{title}". Render those characters clearly and do not add other text.'
            if include_text
            else "Do not render any typography, numerals, labels or fake lettering; leave clean negative space for captions added in post-production."
        )
        composition = "A wide establishing editorial tableau that turns the narration into one instantly understandable visual argument."
    return (
        f"{STYLE_BLOCK} {composition} Subject and evidence: {narration} "
        "Build foreground, middle-ground and background as separate cut-paper pieces with clean silhouettes and real shadows. "
        f"Use a bold flat {background} background. {headline} "
        f"{orientation} {aspect} composition, high detail, crisp edges, no logos, no watermark."
    )


def runninghub_prompt(shot: dict[str, Any]) -> str:
    """Build an I2VA prompt in the official MiniMax H3 three-field structure.

    Screen text is anchored by quoting it verbatim; text-free shots describe
    blank paper as staying blank. Negative-only guards proved ineffective
    against pseudo-text hallucination; positive scene anchoring does not.
    """
    camera = H3_CAMERA_INSTRUCTIONS.get(
        shot["camera_move"],
        "The camera holds a static shot while only the specified paper elements move.",
    )
    element_motion = shot["element_motion"].strip().rstrip(".")
    if shot.get("headline") and shot.get("text_safe", shot.get("title", False)):
        text_clause = (
            f'A torn paper banner carries bold printed Chinese characters reading "{shot["headline"]}", '
            "and these printed characters remain a fixed pasted layer, pixel-stable and unchanged for the whole clip. "
        )
    else:
        text_clause = (
            "Every blank paper area remains plain blank textured paper throughout the clip, "
            "with no letters, numerals, signs or labels anywhere in the frame. "
        )
    description = (
        "[Shot 1] 2D vintage editorial paper-collage cut-out animation, composed exactly as in <Picture 1>: "
        "clearly separated torn-paper layers with visible print grain, tape marks and soft paper shadows "
        f"turn the narration into one visual argument: {shot.get('scene', '')} "
        f"{text_clause}"
        f"{camera} The paper action unfolds in gentle tactile increments: {element_motion}. "
        "The composition stays flat and front-facing while the layers breathe with faint print grain."
    )
    return (
        "For the target video, at 0.00 seconds into the target video, <Picture 1> (from [Shot 1]) is fully referenced.\n\n"
        f"integrated_multimodal_description: {description}\n\n"
        "overall_soundscape: Faint paper rustle over a soft low room tone, "
        "with the tactile scrapes of cut-paper pieces settling.\n\n"
        "non_diegetic_music: N/A"
    )


def create_plan(
    project_name: str,
    script_path: Path,
    output_path: Path,
    aspect: str = "9:16",
    target_beat_seconds: float = 9.0,
    shots_per_beat: int = 2,
) -> dict[str, Any]:
    script = script_path.read_text(encoding="utf-8-sig").strip()
    groups = group_sentences(split_sentences(script), target_beat_seconds)
    if not groups:
        raise ValueError("Script is empty")
    beats: list[dict[str, Any]] = []
    shot_number = 0
    for index, narration in enumerate(groups, start=1):
        title = title_from_text(narration)
        beat_seconds = estimate_seconds(narration)
        shot_count = shots_per_beat if beat_seconds >= 6.5 else 1
        shots = []
        for local in range(shot_count):
            shot_number += 1
            detail = local > 0
            shot = {
                "id": f"{shot_number:03d}",
                "beat_id": index,
                "kind": "detail" if detail else "wide",
                "title": not detail,
                "text_safe": not detail,
                "headline": "" if detail else title,
                "duration": 5,
                "camera_move": CAMERA_MOVES[(shot_number - 1) % len(CAMERA_MOVES)],
                "element_motion": ELEMENT_MOTIONS[(shot_number - 1) % len(ELEMENT_MOTIONS)],
                "scene": narration,
            }
            shot["image_prompt"] = image_prompt(
                narration, title, BACKGROUNDS[(index - 1) % len(BACKGROUNDS)], detail, aspect
            )
            shot["video_prompt"] = runninghub_prompt(shot)
            shots.append(shot)
        beats.append(
            {
                "id": index,
                "title_cn": title,
                "narration": narration,
                "estimated_seconds": round(beat_seconds, 2),
                "background": BACKGROUNDS[(index - 1) % len(BACKGROUNDS)],
                "shots": shots,
            }
        )
    plan = {
        "schema_version": 1,
        "project": project_name,
        "aspect": aspect,
        "style": "editorial-paper-collage",
        "script_path": str(script_path.resolve()),
        "script_sha256": sha256_text(script),
        "estimated_duration": round(sum(item["estimated_seconds"] for item in beats), 2),
        "beats": beats,
    }
    write_json(output_path, plan)
    return plan


def iter_shots(plan: dict[str, Any]):
    for beat in plan["beats"]:
        for shot in beat["shots"]:
            yield beat, shot
