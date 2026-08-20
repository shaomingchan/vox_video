"""
内置的 Image 生成适配器

不依赖 whiteboard 项目，直接调用 API
"""
from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Any

# 提示：这是一个简化版内置适配器
# 如果你有 whiteboard 项目，可以通过设置 whiteboard_root 使用其完整功能


async def generate_image_builtin(prompt: str, aspect_ratio: str, output_dir: Path, index: int) -> Path:
    """
    内置图片生成函数（占位实现）
    
    TODO: 接入实际的图片生成 API
    - 可以接入 OpenAI DALL-E
    - 可以接入 Replicate FLUX
    - 可以接入其他 image2 服务
    """
    raise NotImplementedError(
        "内置图片生成器尚未实现。\n"
        "请配置 whiteboard_root 路径，或等待未来版本的内置实现。\n"
        f"提示词: {prompt[:100]}..."
    )


async def run_batch_builtin(tasks: list[dict[str, Any]], concurrency: int) -> list[str | Exception]:
    """
    批量生成图片（内置实现）
    """
    semaphore = asyncio.Semaphore(concurrency)
    
    async def generate_one(task: dict[str, Any]) -> str | Exception:
        async with semaphore:
            try:
                result = await generate_image_builtin(
                    prompt=task["prompt"],
                    aspect_ratio=task["aspectRatio"],
                    output_dir=Path(task["outputDir"]),
                    index=task["index"]
                )
                return str(result)
            except Exception as e:
                return e
    
    return await asyncio.gather(*[generate_one(task) for task in tasks])


def has_builtin_support() -> bool:
    """检查是否支持内置图片生成"""
    # TODO: 检查环境变量中是否有图片生成 API Key
    # 例如：OPENAI_API_KEY, REPLICATE_API_TOKEN 等
    return False


def get_builtin_info() -> str:
    """获取内置适配器信息"""
    if os.getenv("OPENAI_API_KEY"):
        return "OpenAI DALL-E (通过 OPENAI_API_KEY)"
    if os.getenv("REPLICATE_API_TOKEN"):
        return "Replicate API (通过 REPLICATE_API_TOKEN)"
    return "未配置（需要 whiteboard 或 API Key）"
