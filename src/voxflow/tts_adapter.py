from __future__ import annotations

import json
import os
import tempfile
import sys
from pathlib import Path
from typing import Any

from .util import media_duration, read_json, sha256_text, write_json


def _load_builtin_env() -> None:
    """加载 adapters/.env 中的密钥到环境变量（不覆盖已有值）"""
    env_path = Path(__file__).parent / "adapters" / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and value and not os.environ.get(key):
            os.environ[key] = value


def _build_tts_config(settings: dict[str, Any]) -> str:
    """根据环境变量构建 TTS config.ini 内容"""
    provider = os.environ.get("TTS_PROVIDER", "minimax")
    concurrency = settings.get("tts", {}).get("concurrency", 1)
    
    sections = [f"[TTS]\nprovider = {provider}\nconcurrency = {concurrency}\nretries = 3"]
    
    # MiniMax 配置
    minimax_key = os.environ.get("MINIMAX_API_KEY") or os.environ.get("AI302_API_KEY")
    if minimax_key:
        sections.append(
            "[MiniMax]\n"
            f"api_key = {minimax_key}\n"
            f"api_url = {os.environ.get('MINIMAX_API_URL', 'https://api.302.ai/minimaxi/v1/t2a_v2')}\n"
            f"model = {os.environ.get('MINIMAX_TTS_MODEL', 'speech-2.8-turbo')}\n"
            f"voice_id = {os.environ.get('MINIMAX_VOICE_ID', 'Chinese (Mandarin)_Warm_Bestie')}\n"
            "speed = 1\nvol = 1\npitch = 0\n"
            "text_normalization = true\nsubtitle_type = word\noutput_format = url\n"
            "timeout = 600\nmax_chars = 9000"
        )
    
    # RunningHub TTS 配置
    rh_key = os.environ.get("RUNNINGHUB_API_KEY") or os.environ.get("RUNNINGHUB_TTS_API_KEY")
    if rh_key:
        sections.append(f"[RunningHub]\napi_key = {rh_key}")
        sections.append(f"[RunningHubTTS]\napi_key = {rh_key}")
    
    # FishAudio 配置
    fish_key = os.environ.get("FISH_AUDIO_API_KEY")
    if fish_key:
        sections.append(
            "[FishAudio]\n"
            f"api_key = {fish_key}\n"
            f"reference_id = {os.environ.get('FISH_AUDIO_REFERENCE_ID', '')}\n"
            f"model = {os.environ.get('FISH_AUDIO_MODEL', 's2-pro')}\n"
            "format = mp3\nlatency = normal\ntimeout = 180"
        )
    
    # IndexTTS2 配置
    index_key = os.environ.get("INDEX_TTS2_API_KEY") or os.environ.get("AI302_API_KEY")
    if index_key:
        sections.append(
            "[IndexTTS2]\n"
            f"api_key = {index_key}\n"
            f"speaker_audio_url = {os.environ.get('INDEX_TTS2_SPEAKER_AUDIO_URL', '')}\n"
            "concurrency = 1\ntimeout = 60\npoll_interval = 2.0\nmax_wait_seconds = 900"
        )
    
    return "\n\n".join(sections) + "\n"


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
        # 加载内置密钥
        _load_builtin_env()
        
        # 将 adapters 目录添加到路径
        adapter_dir = Path(__file__).parent / "adapters"
        if str(adapter_dir) not in sys.path:
            sys.path.insert(0, str(adapter_dir))
        
        # 导入 TTS 生成模块
        import tts_generation
        
        # 创建临时 config.ini（从环境变量构建完整配置）
        config_content = _build_tts_config(settings)
        config_file = tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", suffix=".ini", prefix="voxflow-tts-", delete=False
        )
        config_path = Path(config_file.name)
        config_file.write(config_content)
        config_file.close()
        
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
        try:
            result = tts_generation.main()
        finally:
            sys.argv = old_argv
            config_path.unlink(missing_ok=True)
        
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
