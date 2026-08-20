# VoxFlow 自动化配置脚本（AI Agent 专用）

import os
import sys
import json
import shutil
from pathlib import Path

def setup_voxflow():
    """自动化配置 VoxFlow"""
    
    print("🤖 VoxFlow AI Agent 自动配置")
    print("=" * 60)
    
    # 1. 检查必要的 API Key
    required_keys = {
        "RUNNINGHUB_API_KEY": "RunningHub API Key（用于视频生成）",
    }
    
    missing_keys = []
    for key, description in required_keys.items():
        if not os.getenv(key):
            missing_keys.append(f"  - {key}: {description}")
    
    if missing_keys:
        print("❌ 缺少必要的环境变量：\n")
        print("\n".join(missing_keys))
        print("\n请设置这些环境变量后重新运行。")
        print("\n示例（PowerShell）：")
        print('  $env:RUNNINGHUB_API_KEY = "your-key-here"')
        print("\n示例（Bash）：")
        print('  export RUNNINGHUB_API_KEY="your-key-here"')
        return False
    
    print("✅ 环境变量已设置")
    
    # 2. 检查 whiteboard 适配器
    whiteboard_root = os.getenv("WHITEBOARD_ROOT")
    if whiteboard_root and Path(whiteboard_root).exists():
        print(f"✅ 检测到 whiteboard 项目：{whiteboard_root}")
    else:
        print("⚠️  未检测到 whiteboard 项目路径")
        print("   将使用项目内置的适配器（如果可用）")
    
    # 3. 生成配置文件
    config_path = Path("config.local.toml")
    if config_path.exists():
        print(f"✅ 配置文件已存在：{config_path}")
    else:
        print("📝 生成默认配置文件...")
        shutil.copy("config.example.toml", config_path)
        
        # 自动填充路径
        config_content = config_path.read_text(encoding="utf-8")
        
        # 如果有 whiteboard 路径，自动填充
        if whiteboard_root:
            config_content = config_content.replace(
                'whiteboard_root = ""',
                f'whiteboard_root = "{whiteboard_root}"'
            )
        
        # 尝试找到 vox-director skill
        codex_skill = Path.home() / ".codex/skills/vox-director"
        claude_skill = Path.home() / ".claude/skills/vox-director"
        
        if codex_skill.exists():
            config_content = config_content.replace(
                '# vox_director_root = ""',
                f'vox_director_root = "{codex_skill}"'
            )
        elif claude_skill.exists():
            config_content = config_content.replace(
                '# vox_director_root = ""',
                f'vox_director_root = "{claude_skill}"'
            )
        
        config_path.write_text(config_content, encoding="utf-8")
        print(f"✅ 配置文件已生成：{config_path}")
    
    # 4. 安装 Python 依赖
    print("\n📦 安装 Python 依赖...")
    try:
        import subprocess
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "-e", "."],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            print("✅ 依赖安装成功")
        else:
            print(f"⚠️  依赖安装警告：\n{result.stderr}")
    except Exception as e:
        print(f"❌ 依赖安装失败：{e}")
        return False
    
    # 5. 创建必要目录
    directories = ["projects", "outputs", "inputs"]
    for dir_name in directories:
        Path(dir_name).mkdir(exist_ok=True)
    print(f"✅ 项目目录已创建：{', '.join(directories)}")
    
    # 6. 运行健康检查
    print("\n🔍 运行健康检查...")
    try:
        if sys.platform == "win32":
            result = subprocess.run(
                ["powershell", "-File", "scripts/voxflow.ps1", "doctor"],
                capture_output=True,
                text=True
            )
        else:
            # 为非 Windows 系统提供 Python 版本的 doctor
            result = subprocess.run(
                [sys.executable, "-m", "voxflow.cli", "doctor"],
                capture_output=True,
                text=True
            )
        
        print(result.stdout)
        if result.returncode != 0:
            print("⚠️  健康检查发现问题，但可以继续")
            print(result.stderr)
    except Exception as e:
        print(f"⚠️  无法运行健康检查：{e}")
    
    print("\n" + "=" * 60)
    print("🎉 VoxFlow 配置完成！")
    print("\n快速开始：")
    print("  1. 运行 demo（3 个镜头小样）：")
    print("     scripts/voxflow.ps1 run --project demo --script examples/demo-script.txt --limit 3")
    print("\n  2. 查看生成的视频：")
    print("     projects/demo/final/")
    
    return True

if __name__ == "__main__":
    success = setup_voxflow()
    sys.exit(0 if success else 1)
