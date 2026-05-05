from __future__ import annotations

import os
from pathlib import Path


def load_dotenv(path: str | Path = ".env") -> list[str]:
    """加载 .env 文件中的环境变量，不覆盖已存在的系统环境变量。"""
    dotenv_path = Path(path)
    if not dotenv_path.exists():
        return []

    loaded: list[str] = []
    for line in dotenv_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key or key in os.environ:
            continue
        os.environ[key] = value
        loaded.append(key)
    return loaded
