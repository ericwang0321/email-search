#!/usr/bin/env python3
"""
跨平台启动脚本 - 自动检测操作系统，使用正确的虚拟环境路径
用法:
    python run.py "搜索关键词" [top_k] [sync_days]
"""
import sys
import os
import platform
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent
SCRIPTS_DIR = SKILL_DIR / "Bundled Resources" / "scripts"

# 自动检测虚拟环境中的 Python 路径
if platform.system() == "Windows":
    VENV_PYTHON = SKILL_DIR / ".venv" / "Scripts" / "python.exe"
else:
    VENV_PYTHON = SKILL_DIR / ".venv" / "bin" / "python"

# 将 scripts 目录加入 Python 路径（兼容直接用 venv python 调用的情况）
sys.path.insert(0, str(SCRIPTS_DIR))

if __name__ == "__main__":
    # 如果当前就是 venv 中的 python，直接运行
    from email_knowledge_tool import search_email_knowledge_base

    query = sys.argv[1] if len(sys.argv) >= 2 else None
    top_k = int(sys.argv[2]) if len(sys.argv) >= 3 else 3
    sync_days = int(sys.argv[3]) if len(sys.argv) >= 4 else None

    if not query:
        print("用法: python run.py \"搜索关键词\" [top_k] [sync_days]")
        sys.exit(1)

    os.environ["PYTHONIOENCODING"] = "utf-8"
    result = search_email_knowledge_base(query=query, top_k=top_k, sync_days=sync_days)
    print(result)
