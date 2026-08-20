"""Check local prerequisites before configuring or running VoxFlow."""

from __future__ import annotations

import subprocess
import sys


def check_python_version() -> tuple[bool, str]:
    version = sys.version_info
    if version < (3, 11):
        return False, f"需要 Python 3.11+，当前版本：{version.major}.{version.minor}"
    return True, f"Python {version.major}.{version.minor}.{version.micro}"


def check_command(command: str, label: str, args: tuple[str, ...]) -> tuple[bool, str]:
    try:
        result = subprocess.run(
            [command, *args],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        if result.returncode != 0:
            return False, f"{label} 未正确安装"
        output = (result.stdout or result.stderr).splitlines()
        return True, output[0] if output else f"{label} 可用"
    except FileNotFoundError:
        return False, f"{label} 未安装"
    except Exception as exc:  # pragma: no cover - defensive environment check
        return False, f"{label} 检查失败：{exc}"


def run_preflight_check() -> bool:
    checks = {
        "Python 3.11+": check_python_version(),
        "FFmpeg": check_command("ffmpeg", "FFmpeg", ("-version",)),
        "Git": check_command("git", "Git", ("--version",)),
    }

    print("VoxFlow 环境预检查")
    print("=" * 60)
    all_passed = True
    for name, (passed, message) in checks.items():
        print(f"{'[OK]' if passed else '[FAIL]'} {name}: {message}")
        all_passed = all_passed and passed
    print("=" * 60)

    if not all_passed:
        print("\n❌ 环境检查未通过，请先安装缺失的依赖")
        if not checks["Python 3.11+"][0]:
            print("  Python: https://www.python.org/downloads/")
        if not checks["FFmpeg"][0]:
            print("  FFmpeg: https://ffmpeg.org/download.html")
        if not checks["Git"][0]:
            print("  Git: https://git-scm.com/downloads")
        return False

    print("\n环境检查通过！")
    return True


if __name__ == "__main__":
    raise SystemExit(0 if run_preflight_check() else 1)
