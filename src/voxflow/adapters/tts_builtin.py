"""
内置的 TTS 适配器

不依赖 whiteboard 项目，直接调用 TTS API
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any


def generate_tts_builtin(
    text: str,
    output_path: Path,
    voice: str = "alloy"
) -> Path:
    """
    内置 TTS 生成函数（占位实现）
    
    TODO: 接入实际的 TTS API
    - 可以接入 OpenAI TTS
    - 可以接入 Azure TTS
    - 可以接入 ElevenLabs
    """
    raise NotImplementedError(
        "内置 TTS 生成器尚未实现。\n"
        "请配置 whiteboard_root 路径，或等待未来版本的内置实现。\n"
        f"文本: {text[:100]}..."
    )


def has_builtin_tts_support() -> bool:
    """检查是否支持内置 TTS"""
    # TODO: 检查环境变量中是否有 TTS API Key
    return False


def get_builtin_tts_info() -> str:
    """获取内置 TTS 适配器信息"""
    if os.getenv("OPENAI_API_KEY"):
        return "OpenAI TTS (通过 OPENAI_API_KEY)"
    if os.getenv("AZURE_SPEECH_KEY"):
        return "Azure TTS (通过 AZURE_SPEECH_KEY)"
    return "未配置（需要 whiteboard 或 API Key）"
