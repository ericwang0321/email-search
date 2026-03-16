import base64
import json
import os
from datetime import datetime, timezone
from typing import Optional

from graph_client import build_client, _get, _GRAPH_BASE
from config import (
    SYNC_STATE_FILE,
    RAW_DATA_DIR,
    sanitize_filename,
    DEFAULT_SYNC_START_DATE,
    DEFAULT_SYNC_DAYS,
    PAGE_SIZE,
    MAX_ATTACHMENT_SIZE,
    ensure_dirs_exist,
)


def load_last_sync_time() -> str:
    """读取上次同步的时间。如果没有，则从30天前开始"""
    if not os.path.exists(SYNC_STATE_FILE):
        return DEFAULT_SYNC_START_DATE

    try:
        with open(SYNC_STATE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("last_sync_time", DEFAULT_SYNC_START_DATE)
    except (json.JSONDecodeError, IOError) as e:
        print(f"⚠️ 读取同步状态失败，使用默认值: {e}")
        return DEFAULT_SYNC_START_DATE


def save_sync_time(sync_time: str):
    """保存本次同步的时间，用于断点续传"""
    try:
        with open(SYNC_STATE_FILE, "w", encoding="utf-8") as f:
            json.dump({"last_sync_time": sync_time}, f, indent=4)
    except IOError as e:
        print(f"❌ 保存同步状态失败: {e}")
        raise


def download_attachments(client, message_id: str, save_dir: str) -> list[str]:
    """
    下载附件并保存
    返回: 成功下载的文件路径列表
    """
    url = f"{_GRAPH_BASE}/users/{client.email}/messages/{message_id}/attachments"
    data = _get(url, client.headers)

    downloaded_files = []
    for att in data.get("value", []):
        if att.get("@odata.type") != "#microsoft.graph.fileAttachment":
            continue

        file_name = sanitize_filename(att.get("name", "unknown_file"))
        content_bytes = att.get("contentBytes")

        if not content_bytes:
            print(f"     ⚠️ 附件 {file_name} 内容为空，跳过")
            continue

        # 检查文件大小
        decoded_size = len(base64.b64decode(content_bytes))
        if decoded_size > MAX_ATTACHMENT_SIZE:
            print(f"     ⚠️ 附件 {file_name} 超过大小限制 ({decoded_size / 1024 / 1024:.2f}MB)，跳过")
            continue

        file_path = os.path.join(save_dir, file_name)
        try:
            with open(file_path, "wb") as f:
                f.write(base64.b64decode(content_bytes))
            downloaded_files.append(file_path)
            print(f"     ✓ 已下载: {file_name}")
        except (IOError, OSError) as e:
            print(f"     ❌ 下载附件失败 {file_name}: {e}")

    return downloaded_files


def get_email_dir_name(date_str: str, subject: str) -> str:
    """
    生成邮件存储目录名
    格式: YYYY-MM-DD_subject
    subject 会被清理并限制长度
    """
    date_prefix = date_str.split("T")[0]
    safe_subject = sanitize_filename(subject, max_length=50)
    return f"{date_prefix}_{safe_subject}"


def run_incremental_sync(sync_days: int = None) -> int:
    """
    运行增量同步
    返回: 成功同步的邮件数量

    参数:
    - sync_days: 同步过去多少天的邮件。None 表示使用默认值（30天）
      示例:
        - sync_days=7    # 同步过去7天
        - sync_days=30   # 同步过去30天（默认）
        - sync_days=365  # 同步过去1年
    """
    print("🔄 初始化增量同步引擎...")
    ensure_dirs_exist()

    client = build_client()

    # 根据 sync_days 参数计算同步起始时间
    if sync_days is not None:
        # 使用上次同步时间继续增量同步
        last_sync = load_last_sync_time()
        print(f"📅 上次同步时间: {last_sync}")
        print(f"📭 当前目标邮箱: {client.email}")
        print("\n🔍 正在查找新邮件（增量模式）...")
        filter_query = f"receivedDateTime gt {last_sync}"
    else:
        # 根据 sync_days 重新计算起始时间
        start_date = (datetime.now(timezone.utc) - timedelta(days=sync_days)).strftime("%Y-%m-%dT%H:%M:%SZ")
        print(f"📅 同步范围: 过去 {sync_days} 天")
        print(f"📅 起始时间: {start_date}")
        print(f"📭 当前目标邮箱: {client.email}")
        print(f"\n🔍 正在查找过去 {sync_days} 天的邮件（全量模式）...")
        filter_query = f"receivedDateTime ge {start_date}"
        # 更新 last_sync 为本次起始时间
        save_sync_time(start_date)
        last_sync = start_date

    url = f"{_GRAPH_BASE}/users/{client.email}/mailFolders/inbox/messages"
    params = {
        "$select": "id,subject,receivedDateTime,hasAttachments,body",
        "$filter": filter_query,
        "$orderby": "receivedDateTime asc",  # 按时间正序，保证断点续传逻辑正确
        "$top": PAGE_SIZE,
    }

    new_emails_count = 0
    synced_times = []  # 批量记录成功处理的时间戳

    try:
        while url:
            data = _get(url, client.headers, params)
            messages = data.get("value", [])

            for msg in messages:
                msg_id = msg.get("id")
                subject = msg.get("subject", "无主题")
                date_str = msg.get("receivedDateTime")

                if not date_str:
                    print(f"  ⚠️ 邮件缺少时间戳，跳过")
                    continue

                print(f"  📥 处理新邮件: [{date_str}] {subject[:40]}...")

                try:
                    # 生成目录名
                    email_dir_name = get_email_dir_name(date_str, subject)
                    email_dir = os.path.join(str(RAW_DATA_DIR), email_dir_name)
                    os.makedirs(email_dir, exist_ok=True)

                    # 保存正文
                    body_content = msg.get("body", {}).get("content", "")
                    if body_content:
                        body_path = os.path.join(email_dir, "body.txt")
                        with open(body_path, "w", encoding="utf-8") as f:
                            f.write(body_content)

                    # 下载附件
                    if msg.get("hasAttachments"):
                        download_attachments(client, msg_id, email_dir)

                    # 记录成功的时间戳
                    synced_times.append(date_str)
                    new_emails_count += 1

                except (IOError, OSError) as e:
                    print(f"     ❌ 处理邮件失败: {e}")
                    continue

            url = data.get("@odata.nextLink")
            params = None

    except Exception as e:
        print(f"\n❌ 同步过程中发生错误: {e}")
        # 仍然保存已经成功的邮件时间戳
        if synced_times:
            print(f"💾 保存已同步的 {len(synced_times)} 封邮件的时间戳")
            save_sync_time(synced_times[-1])
        raise

    # 批量保存最新的时间戳
    if synced_times:
        save_sync_time(synced_times[-1])

    if new_emails_count == 0:
        if sync_days is None:
            print("\n✅ 没有发现新邮件，知识库已是最新状态。")
        else:
            print(f"\n✅ 同步完成！在过去的 {sync_days} 天中找到 {new_emails_count} 封邮件。")
    else:
        if sync_days is None:
            print(f"\n🎉 成功同步了 {new_emails_count} 封新邮件！")
        else:
            print(f"\n🎉 成功同步了 {new_emails_count} 封邮件（过去 {sync_days} 天）！")

    return new_emails_count


if __name__ == "__main__":
    run_incremental_sync()
