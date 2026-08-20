# VoxFlow AI Agent 自动化部署指南

本文档专门为 AI Agent（Claude Code, Codex, Workbuddy 等）设计，确保 Agent 能够自动完成 VoxFlow 的配置和运行。

## 自动化配置检查清单

AI Agent 应该按以下顺序执行：

### 1. 环境检查

```python
# agents/preflight_check.py
import sys
import subprocess
import os
from pathlib import Path

def check_python_version():
    """检查 Python 3.11+"""
    version = sys.version_info
    if version < (3, 11):
        return False, f"需要 Python 3.11+，当前版本：{version.major}.{version.minor}"
    return True, f"Python {version.major}.{version.minor}.{version.micro}"

def check_ffmpeg():
    """检查 FFmpeg"""
    try:
        result = subprocess.run(["ffmpeg", "-version"], 
                              capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            version = result.stdout.split('\n')[0]
            return True, version
        return False, "FFmpeg 未正确安装"
    except FileNotFoundError:
        return False, "FFmpeg 未安装"
    except Exception as e:
        return False, f"FFmpeg 检查失败：{str(e)}"

def check_git():
    """检查 Git"""
    try:
        result = subprocess.run(["git", "--version"],
                              capture_output=True, text=True, timeout=5)
        return result.returncode == 0, result.stdout.strip()
    except:
        return False, "Git 未安装"

def run_preflight_check():
    """运行预检查"""
    checks = {
        "Python 3.11+": check_python_version(),
        "FFmpeg": check_ffmpeg(),
        "Git": check_git(),
    }
    
    print("VoxFlow 环境预检查")
    print("=" * 60)
    
    all_passed = True
    for name, (passed, message) in checks.items():
        status = "✅" if passed else "❌"
        print(f"{status} {name}: {message}")
        if not passed:
            all_passed = False
    
    print("=" * 60)
    
    if not all_passed:
        print("\n❌ 环境检查未通过，请先安装缺失的依赖")
        print("\n安装指南：")
        if not checks["Python 3.11+"][0]:
            print("  Python: https://www.python.org/downloads/")
        if not checks["FFmpeg"][0]:
            print("  FFmpeg: https://ffmpeg.org/download.html")
            print("    Windows: winget install ffmpeg")
            print("    Mac: brew install ffmpeg")
            print("    Linux: apt install ffmpeg")
        if not checks["Git"][0]:
            print("  Git: https://git-scm.com/downloads")
        sys.exit(1)
    
    print("\n✅ 环境检查通过！")
    return True

if __name__ == "__main__":
    run_preflight_check()
