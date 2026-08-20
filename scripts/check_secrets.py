"""Fail closed when likely credentials are present in publishable files."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path


PATTERNS = (
    ("hex-32-token", re.compile(r"\b[a-fA-F0-9]{32}\b")),
    ("github-token", re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{20,}\b")),
    ("openai-token", re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b")),
    ("bearer-token", re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]{16,}")),
    (
        "assignment-secret",
        re.compile(
            r"(?i)\b(?:api[_-]?key|secret|password|token)\b\s*[:=]\s*['\"]?[A-Za-z0-9._~+/=-]{16,}"
        ),
    ),
)

EXCLUDED_PARTS = {
    ".git",
    ".venv",
    "__pycache__",
    ".pytest_cache",
    "node_modules",
    "projects",
    "outputs",
    "inputs",
    "media",
    "renders",
}
EXCLUDED_NAMES = {"config.toml", "config.local.toml"}


def candidate_files(root: Path) -> list[Path]:
    try:
        result = subprocess.run(
            ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
        )
        paths = [root / line for line in result.stdout.splitlines() if line]
    except (OSError, subprocess.CalledProcessError):
        paths = list(root.rglob("*"))
    return [
        path
        for path in paths
        if path.is_file()
        and path.name not in EXCLUDED_NAMES
        and not any(part in EXCLUDED_PARTS for part in path.parts)
    ]


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    findings: list[str] = []
    for path in candidate_files(root):
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for line_number, line in enumerate(text.splitlines(), start=1):
            for label, pattern in PATTERNS:
                if pattern.search(line):
                    findings.append(f"{path.relative_to(root)}:{line_number}: {label}")
                    break
    if findings:
        print("Potential credentials found:", file=sys.stderr)
        print("\n".join(findings), file=sys.stderr)
        return 1
    print("Secret scan passed: no credential-shaped values found.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
