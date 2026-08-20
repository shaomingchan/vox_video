from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from .util import media_duration, read_json, sha256_text, write_json


def generate_voice(
    settings: dict[str, Any], project: Path, force: bool = False
) -> dict[str, Any]:
    """使用内置 TTS 适配器生成口播和字幕"""
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

    # 使用内置 TTS 生成器（调用 tts_generation.py 作为模块）
    try:
        # 将 adapters 目录添加到路径
        adapter_dir = Path(__file__).parent / "adapters"
        if str(adapter_dir) not in sys.path:
            sys.path.insert(0, str(adapter_dir))
        
        # 导入 TTS 生成模块
        import tts_generation
        
        # 创建临时 config.ini（使用环境变量）
        config_content = f"""
[TTS]
provider = {os.environ.get('TTS_PROVIDER', 'runninghub')}
voice_id = default
concurrency = {settings["tts"].get("concurrency", 1)}

[RunningHub]
api_key = {os.environ.get('RUNNINGHUB_API_KEY', '')}
"""
        config_path = audio_dir / "config.ini"
        config_path.write_text(config_content, encoding="utf-8")
        
        # 调用 TTS 生成（使用内置模块的 main 逻辑）
        import argparse
        old_argv = sys.argv
        sys.argv = [
            "tts_generation.py",
            "--sentences", str(sentences_path.resolve()),
            "--output-dir", str(audio_dir.resolve()),
            "--config", str(config_path.resolve()),
            "--source-text", str(script_path.resolve()),
            "--concurrency", str(settings["tts"].get("concurrency", 1)),
        ]
        if force:
            sys.argv.append("--force-tts")
        
        # 运行 TTS
        result = tts_generation.main()
        sys.argv = old_argv
        
        # 读取结果
        voiceover = audio_dir / "voiceover.wav"
        subtitles = audio_dir / "subtitles.srt"
        
        if not voiceover.exists() or not subtitles.exists():
            raise RuntimeError("TTS generation did not produce output files")
        
        manifest = {
            "voiceover_path": str(voiceover.resolve()),
            "srt_path": str(subtitles.resolve()),
            "duration": media_duration(voiceover),
            "fingerprint": fingerprint,
        }
        write_json(manifest_path, manifest)
        return manifest
        
    except ImportError as e:
        raise RuntimeError(
            f"无法加载内置 TTS 适配器: {e}\n"
            "请确保 src/voxflow/adapters/tts_generation.py 存在"
        )
    except Exception as e:
        raise RuntimeError(f"TTS generation failed: {e}")
