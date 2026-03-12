import base64
import json
import os
from datetime import datetime, timezone
from pathlib import Path

# 请确保同目录下有 graph_client.py 并且包含了下面这些函数和变量
from graph_client import build_client, _get, _GRAPH_BASE

SYNC_STATE_FILE = "../assets/sync_state.json"
RAW_DATA_DIR = "../assets/knowledge_base/raw_data"

def load_last_sync_time() -> str:
    """读取上次同步的时间。如果没有，则默认从 2026-01-01 开始"""
    if os.path.exists(SYNC_STATE_FILE):
        with open(SYNC_STATE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("last_sync_time", "2026-01-01T00:00:00Z")
    return "2026-01-01T00:00:00Z"

def save_sync_time(sync_time: str):
    """保存本次同步的时间，用于断点续传"""
    with open(SYNC_STATE_FILE, "w", encoding="utf-8") as f:
        json.dump({"last_sync_time": sync_time}, f, indent=4)

def download_attachments(client, message_id: str, save_dir: str) -> list[str]:
    """下载附件并保存"""
    url = f"{_GRAPH_BASE}/users/{client.email}/messages/{message_id}/attachments"
    data = _get(url, client.headers)
    
    downloaded_files = []
    for att in data.get("value", []):
        if att.get("@odata.type") == "#microsoft.graph.fileAttachment":
            # 过滤掉文件名中可能导致路径错误的非法字符
            file_name = att.get("name", "unknown_file").replace("/", "_").replace("\\", "_")
            content_bytes = att.get("contentBytes")
            
            if content_bytes:
                file_path = os.path.join(save_dir, file_name)
                with open(file_path, "wb") as f:
                    f.write(base64.b64decode(content_bytes))
                downloaded_files.append(file_path)
    return downloaded_files

def run_incremental_sync():
    print("🔄 初始化增量同步引擎...")
    client = build_client()
    last_sync = load_last_sync_time()
    print(f"📅 上次同步时间: {last_sync}")
    print(f"📭 当前目标邮箱: {client.email}")
    
    print("\n🔍 正在查找新邮件...")
    
    # 构造 filter 条件，严格查找大于上次同步时间的邮件
    filter_query = f"receivedDateTime gt {last_sync}"
    
    url = f"{_GRAPH_BASE}/users/{client.email}/mailFolders/inbox/messages"
    params = {
        "$select": "id,subject,receivedDateTime,hasAttachments,body",
        "$filter": filter_query,
        "$orderby": "receivedDateTime asc", # ⚠️ 必须按时间正序（从老到新），保证断点续传的逻辑正确
        "$top": 50
    }

    new_emails_count = 0
    
    while url:
        data = _get(url, client.headers, params)
        messages = data.get("value", [])
        
        for msg in messages:
            new_emails_count += 1
            msg_id = msg.get("id")
            subject = msg.get("subject", "无主题").replace("/", "_").replace("\\", "_")
            date_str = msg.get("receivedDateTime")
            
            print(f"  📥 处理新邮件: [{date_str}] {subject[:40]}...")
            
            # 为每封邮件创建一个独立的文件夹存放正文和附件
            date_prefix = date_str.split("T")[0]
            # 限制文件夹名称长度，防止路径过长报错
            safe_subject = subject[:30].strip()
            email_dir = os.path.join(RAW_DATA_DIR, f"{date_prefix}_{safe_subject}")
            os.makedirs(email_dir, exist_ok=True)
            
            # 1. 保存正文为 txt
            body_content = msg.get("body", {}).get("content", "")
            if body_content:
                with open(os.path.join(email_dir, "body.txt"), "w", encoding="utf-8") as f:
                    f.write(body_content)
            
            # 2. 下载附件 (加入容错机制)
            if msg.get("hasAttachments"):
                try:
                    download_attachments(client, msg_id, email_dir)
                    print(f"     📎 附件已落地至: {email_dir}")
                except Exception as e:
                    print(f"     ❌ 下载附件超时或失败 (将跳过此附件): {e}")

            # 3. ⚠️ 核心修改：存档。每成功处理完一封邮件，立即将它的时间戳覆盖写入 JSON
            save_sync_time(date_str)

        url = data.get("@odata.nextLink")
        params = None # 翻页时不需要再传 params

    if new_emails_count == 0:
        print("\n✅ 没有发现新邮件，知识库已是最新状态。")
    else:
        print(f"\n🎉 成功同步了 {new_emails_count} 封新邮件！")

if __name__ == "__main__":
    run_incremental_sync()