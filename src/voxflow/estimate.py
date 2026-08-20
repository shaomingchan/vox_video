"""
VoxFlow 费用估算工具

根据脚本和配置估算生成成本（图片 + 视频）
"""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from .config import load_config
from .planner import split_sentences, group_sentences, estimate_seconds


# 费用标准（参考价格，实际以服务商为准）
PRICING = {
    "image": {
        "apimart_image2": {
            "name": "APIMart Image2",
            "price_per_image": 0.02,  # 约 ¥0.02/张
            "currency": "CNY",
        }
    },
    "video": {
        "runninghub_h3_member": {
            "name": "RunningHub H3 会员",
            "price_per_5s": 0.10,  # 约 ¥0.10/5秒
            "currency": "CNY",
        },
        "runninghub_h3_enterprise": {
            "name": "RunningHub H3 企业",
            "price_per_5s": 0.08,  # 企业价格更优惠
            "currency": "CNY",
        },
    },
}


def estimate_costs(
    script_text: str,
    settings: dict[str, Any],
) -> dict[str, Any]:
    """估算生成成本"""
    
    # 模拟分镜规划逻辑
    target_beat_seconds = settings["project"]["target_beat_seconds"]
    shots_per_beat = settings["project"]["shots_per_beat"]
    
    # 拆分句子并分组
    sentences = split_sentences(script_text)
    groups = group_sentences(sentences, target_beat_seconds)
    
    # 统计镜头数
    total_shots = 0
    total_duration = 0
    
    for narration in groups:
        beat_seconds = estimate_seconds(narration)
        # 判断镜头数量（与 planner.py 逻辑一致）
        shot_count = shots_per_beat if beat_seconds >= 6.5 else 1
        total_shots += shot_count
        # 每个镜头 5 秒
        total_duration += shot_count * 5
    
    # 图片费用
    image_provider = settings["image"].get("provider", "apimart_image2")
    image_pricing = PRICING["image"].get(image_provider, PRICING["image"]["apimart_image2"])
    image_cost = total_shots * image_pricing["price_per_image"]
    
    # 视频费用
    api_profile = settings["runninghub"].get("api_profile", "member")
    video_key = f"runninghub_h3_{api_profile}"
    video_pricing = PRICING["video"].get(video_key, PRICING["video"]["runninghub_h3_member"])
    # 按 5 秒计费，向上取整
    video_units = (total_duration + 4) // 5
    video_cost = video_units * video_pricing["price_per_5s"]
    
    # TTS 费用（通常免费或极低，暂不计入）
    tts_cost = 0
    
    # 总费用
    total_cost = image_cost + video_cost + tts_cost
    
    return {
        "script_length": len(script_text),
        "total_beats": len(groups),
        "total_shots": total_shots,
        "total_duration": total_duration,
        "aspect": settings["project"]["aspect"],
        "breakdown": {
            "images": {
                "count": total_shots,
                "provider": image_pricing["name"],
                "unit_price": image_pricing["price_per_image"],
                "total": image_cost,
                "currency": image_pricing["currency"],
            },
            "videos": {
                "duration": total_duration,
                "units": video_units,
                "provider": video_pricing["name"],
                "unit_price": video_pricing["price_per_5s"],
                "total": video_cost,
                "currency": video_pricing["currency"],
            },
            "tts": {
                "cost": tts_cost,
                "note": "TTS 费用极低，未计入",
            },
        },
        "total_cost": total_cost,
        "currency": "CNY",
    }


def format_estimate(estimate: dict[str, Any]) -> str:
    """格式化费用估算结果"""
    lines = [
        "=" * 60,
        "VoxFlow 费用估算",
        "=" * 60,
        "",
        "📝 项目信息：",
        f"  脚本长度：{estimate['script_length']} 字符",
        f"  分镜数量：{estimate['total_beats']} 个 beat",
        f"  镜头数量：{estimate['total_shots']} 个镜头",
        f"  视频时长：{estimate['total_duration']} 秒",
        f"  画面比例：{estimate['aspect']}",
        "",
        "💰 费用明细：",
        "",
        f"1. 图片生成（{estimate['breakdown']['images']['provider']}）",
        f"   数量：{estimate['breakdown']['images']['count']} 张",
        f"   单价：¥{estimate['breakdown']['images']['unit_price']:.2f}/张",
        f"   小计：¥{estimate['breakdown']['images']['total']:.2f}",
        "",
        f"2. 视频生成（{estimate['breakdown']['videos']['provider']}）",
        f"   时长：{estimate['breakdown']['videos']['duration']} 秒",
        f"   计费单元：{estimate['breakdown']['videos']['units']} × 5秒",
        f"   单价：¥{estimate['breakdown']['videos']['unit_price']:.2f}/5秒",
        f"   小计：¥{estimate['breakdown']['videos']['total']:.2f}",
        "",
        f"3. TTS 语音合成",
        f"   {estimate['breakdown']['tts']['note']}",
        "",
        "=" * 60,
        f"💵 预估总费用：¥{estimate['total_cost']:.2f} CNY",
        "=" * 60,
        "",
        "⚠️  说明：",
        "  - 以上为参考价格，实际费用以服务商账单为准",
        "  - 使用缓存可以避免重复生成，降低费用",
        "  - 使用 --limit N 可以先生成少量镜头验证",
        "  - 企业账户价格可能有优惠",
        "",
    ]
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="VoxFlow 费用估算")
    parser.add_argument("--script", required=True, help="脚本文件路径")
    parser.add_argument("--config", default="config.local.toml", help="配置文件路径")
    args = parser.parse_args()
    
    # 加载配置
    settings = load_config(Path(args.config))
    
    # 读取脚本
    script_text = Path(args.script).read_text(encoding="utf-8-sig").strip()
    if not script_text:
        print(f"X 脚本文件为空或不存在：{args.script}")
        return 1
    
    # 估算费用
    estimate = estimate_costs(script_text, settings)
    
    # 输出结果（使用 UTF-8 编码）
    import sys
    if sys.platform == 'win32':
        import codecs
        sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    print(format_estimate(estimate))
    
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
