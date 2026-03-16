"""
统一配置模块
管理所有路径、常量和配置项
"""
import os
from pathlib import Path
from datetime import datetime, timedelta, timezone

# 基础路径配置
SCRIPT_DIR = Path(__file__).resolve().parent
ASSETS_DIR = SCRIPT_DIR.parent / "assets"
KNOWLEDGE_BASE_DIR = ASSETS_DIR / "knowledge_base"

# 数据路径
RAW_DATA_DIR = KNOWLEDGE_BASE_DIR / "raw_data"
CHROMA_DB_DIR = KNOWLEDGE_BASE_DIR / "chroma_db"

# 配置文件路径
SYNC_STATE_FILE = ASSETS_DIR / "sync_state.json"
PROCESSED_RECORD = KNOWLEDGE_BASE_DIR / "processed_folders.json"
NEW_CHUNKS_FILE = KNOWLEDGE_BASE_DIR / "new_chunks.json"
DOWNLOAD_CONFIG = ASSETS_DIR / "Download_EQD.yaml"

# 数据库配置
COLLECTION_NAME = "email_knowledge_base"
BATCH_SIZE = 500

# 文本分块配置
CHUNK_SIZE = 800
CHUNK_OVERLAP = 100
CHUNK_SEPARATORS = ["\n\n", "\n", "。", "！", "？", " ", ""]

# 同步配置
DEFAULT_SYNC_START_DATE = (datetime.now(timezone.utc) - timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
DEFAULT_SYNC_DAYS = 30  # 默认同步过去30天
PAGE_SIZE = 50

# 文件限制
MAX_ATTACHMENT_SIZE = 50 * 1024 * 1024  # 50MB


def sanitize_filename(filename: str, max_length: int = 100) -> str:
    """
    清理文件名中的非法字符
    Windows 非法字符: < > : " / \ | ? *
    """
    # 移除或替换非法字符
    invalid_chars = ['<', '>', ':', '"', '/', '\\', '|', '?', '*']
    cleaned = filename
    for char in invalid_chars:
        cleaned = cleaned.replace(char, '_')

    # 去除首尾空格和点
    cleaned = cleaned.strip(' .')

    # 限制长度
    if len(cleaned) > max_length:
        name, ext = os.path.splitext(cleaned)
        cleaned = name[:max_length - len(ext)] + ext

    # 如果为空，返回默认名称
    if not cleaned:
        cleaned = "unnamed"

    return cleaned


def ensure_dirs_exist():
    """确保所有必要的目录存在"""
    RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)
    CHROMA_DB_DIR.mkdir(parents=True, exist_ok=True)
