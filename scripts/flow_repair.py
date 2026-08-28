from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

import cv2
import numpy as np


def cover_image(image: np.ndarray, width: int, height: int) -> np.ndarray:
    source_height, source_width = image.shape[:2]
    scale = max(width / source_width, height / source_height)
    resized = cv2.resize(
        image,
        (round(source_width * scale), round(source_height * scale)),
        interpolation=cv2.INTER_LANCZOS4,
    )
    y = max(0, (resized.shape[0] - height) // 2)
    x = max(0, (resized.shape[1] - width) // 2)
    return resized[y : y + height, x : x + width].copy()


def repair(clip: Path, keyframe: Path, output: Path, crf: int, preset: str) -> None:
    capture = cv2.VideoCapture(str(clip))
    if not capture.isOpened():
        raise RuntimeError(f"Could not open video: {clip}")

    fps = capture.get(cv2.CAP_PROP_FPS) or 24
    width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
    clean = cv2.imread(str(keyframe), cv2.IMREAD_COLOR)
    if clean is None:
        raise RuntimeError(f"Could not open keyframe: {keyframe}")
    clean = cover_image(clean, width, height)

    ok, reference = capture.read()
    if not ok:
        raise RuntimeError(f"Video has no frames: {clip}")

    flow_width = min(480, width)
    flow_height = max(2, round(height * flow_width / width))
    reference_small = cv2.resize(reference, (flow_width, flow_height), interpolation=cv2.INTER_AREA)
    reference_gray = cv2.cvtColor(reference_small, cv2.COLOR_BGR2GRAY)
    grid_x, grid_y = np.meshgrid(
        np.arange(width, dtype=np.float32),
        np.arange(height, dtype=np.float32),
    )

    output.parent.mkdir(parents=True, exist_ok=True)
    command = [
        "ffmpeg",
        "-y",
        "-f",
        "rawvideo",
        "-pix_fmt",
        "bgr24",
        "-s",
        f"{width}x{height}",
        "-r",
        f"{fps:.6f}",
        "-i",
        "-",
        "-an",
        "-c:v",
        "libx264",
        "-preset",
        preset,
        "-crf",
        str(crf),
        "-pix_fmt",
        "yuv420p",
        "-r",
        f"{fps:.6f}",
        "-fps_mode",
        "cfr",
        str(output),
    ]
    encoder = subprocess.Popen(command, stdin=subprocess.PIPE)
    assert encoder.stdin is not None

    frame = reference
    try:
        while True:
            current_small = cv2.resize(frame, (flow_width, flow_height), interpolation=cv2.INTER_AREA)
            current_gray = cv2.cvtColor(current_small, cv2.COLOR_BGR2GRAY)
            backward_flow = cv2.calcOpticalFlowFarneback(
                current_gray,
                reference_gray,
                None,
                0.5,
                4,
                25,
                4,
                7,
                1.5,
                cv2.OPTFLOW_FARNEBACK_GAUSSIAN,
            )
            backward_flow = cv2.GaussianBlur(backward_flow, (0, 0), 2.2)
            magnitude = np.linalg.norm(backward_flow, axis=2, keepdims=True)
            backward_flow *= np.minimum(1.0, 14.0 / np.maximum(magnitude, 1e-6))
            full_flow = cv2.resize(
                backward_flow,
                (width, height),
                interpolation=cv2.INTER_CUBIC,
            )
            full_flow[..., 0] *= width / flow_width
            full_flow[..., 1] *= height / flow_height
            repaired = cv2.remap(
                clean,
                grid_x + full_flow[..., 0],
                grid_y + full_flow[..., 1],
                interpolation=cv2.INTER_LANCZOS4,
                borderMode=cv2.BORDER_REFLECT_101,
            )
            encoder.stdin.write(repaired.tobytes())
            ok, frame = capture.read()
            if not ok:
                break
    finally:
        capture.release()
        encoder.stdin.close()

    return_code = encoder.wait()
    if return_code != 0:
        raise RuntimeError(f"ffmpeg exited with status {return_code}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Transfer H3 motion onto a clean Image2 keyframe."
    )
    parser.add_argument("--clip", type=Path, required=True)
    parser.add_argument("--keyframe", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--crf", type=int, default=16)
    parser.add_argument("--preset", default="medium")
    args = parser.parse_args()
    repair(args.clip, args.keyframe, args.output, args.crf, args.preset)


if __name__ == "__main__":
    main()
