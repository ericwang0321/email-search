import base64
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Generator, Optional

import msal
import requests
import yaml

_GRAPH_BASE = "https://graph.microsoft.com/v1.0"
_CONFIG_PATH = Path(__file__).resolve().parent.parent / "assets" / "Download_EQD.yaml"

# ── 客户端对象 ────────────────────────────────────────────────────────────────

@dataclass
class GraphClient:
    email: str
    headers: dict
    _client_id: str = field(repr=False)
    _tenant_id: str = field(repr=False)

    def __str__(self):
        return f"GraphClient({self.email})"


# ── 构建客户端 ────────────────────────────────────────────────────────────────

def build_client(
    client_id: Optional[str] = None,
    tenant_id: Optional[str] = None,
    client_secret: Optional[str] = None,
    email: Optional[str] = None,
) -> GraphClient:
    """
    构建已认证的 GraphClient。自动从 Download_EQD.yaml 读取所有配置。
    """
    if not all([client_id, tenant_id, client_secret, email]):
        with open(_CONFIG_PATH, encoding="utf-8") as f:
            cfg = yaml.safe_load(f)
        conn = cfg.get("connection", {})
        client_id     = client_id     or conn.get("client_id")
        tenant_id     = tenant_id     or conn.get("tenant_id")
        email         = email         or conn.get("email")
        # 直接从 YAML 读取 client_secret
        client_secret = client_secret or conn.get("client_secret") 

    if not client_secret:
        raise RuntimeError("client_secret 未提供，请在 Download_EQD.yaml 中配置")

    token = _get_token(client_id, tenant_id, client_secret)
    headers = {"Authorization": f"Bearer {token}"}
    return GraphClient(email=email, headers=headers,
                       _client_id=client_id, _tenant_id=tenant_id)


def _get_token(client_id: str, tenant_id: str, client_secret: str) -> str:
    authority = f"https://login.microsoftonline.com/{tenant_id}"
    app = msal.ConfidentialClientApplication(
        client_id=client_id,
        client_credential=client_secret,
        authority=authority,
    )
    result = app.acquire_token_for_client(
        scopes=["https://graph.microsoft.com/.default"]
    )
    if "access_token" not in result:
        raise RuntimeError(f"获取 token 失败：{result.get('error_description', result)}")
    return result["access_token"]


# ── 底层请求（带重试）────────────────────────────────────────────────────────

def _get(url: str, headers: dict, params: dict = None,
         retries: int = 3, backoff: float = 3.0) -> dict:
    for attempt in range(retries):
        resp = requests.get(url, headers=headers, params=params, timeout=30)
        if resp.status_code == 200:
            return resp.json()
        if resp.status_code in (429, 503, 504):
            wait = backoff * (attempt + 1)
            print(f"  ⚠️  Graph API {resp.status_code}，{wait:.0f}s 后重试...")
            time.sleep(wait)
            continue
        raise RuntimeError(f"Graph API 请求失败 ({resp.status_code})：{resp.text}")
    raise RuntimeError(f"Graph API 多次重试后仍失败：{url}")


# ── 目录操作 ──────────────────────────────────────────────────────────────────

def list_folders(client: GraphClient) -> list[dict]:
    """返回 inbox 下所有子目录"""
    url = f"{_GRAPH_BASE}/users/{client.email}/mailFolders/inbox/childFolders"
    data = _get(url, client.headers, {"$top": 100, "$select": "displayName,totalItemCount,id"})
    return data.get("value", [])


def get_folder_id(client: GraphClient, folder_name: str) -> Optional[str]:
    """按名称查找 inbox 子目录，返回其 ID"""
    for f in list_folders(client):
        if f["displayName"] == folder_name:
            return f["id"]
    return None


# ── 邮件查询 ──────────────────────────────────────────────────────────────────

def fetch_messages(
    client: GraphClient,
    *,
    folder: str = "inbox",
    sender: Optional[str] = None,
    since: Optional[str | datetime] = None,
    include_body: bool = False,
    extra_fields: list[str] = None,
    page_size: int = 50,
) -> Generator[dict, None, None]:
    """从指定目录查询邮件，自动翻页，逐条 yield。"""
    _BUILTIN = {"inbox", "archive", "drafts", "sentitems", "deleteditems"}
    if folder.lower() in _BUILTIN:
        folder_id = folder.lower()
    else:
        folder_id = get_folder_id(client, folder)
        if folder_id is None:
            print(f"  ⚠️  未找到子目录 '{folder}'，跳过")
            return

    select = ["id", "subject", "from", "receivedDateTime", "hasAttachments"]
    if include_body:
        select.append("body")
    if extra_fields:
        select.extend(extra_fields)

    filters = []
    if since:
        if isinstance(since, str):
            since = datetime.strptime(since, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        filters.append(f"receivedDateTime ge {since.strftime('%Y-%m-%dT%H:%M:%SZ')}")

    url = f"{_GRAPH_BASE}/users/{client.email}/mailFolders/{folder_id}/messages"
    params: dict = {
        "$select": ",".join(select),
        "$top":    page_size,
    }
    if not sender:
        params["$orderby"] = "receivedDateTime desc"
    if filters:
        params["$filter"] = " and ".join(filters)

    while url:
        data = _get(url, client.headers, params)
        for msg in data.get("value", []):
            yield msg
        url    = data.get("@odata.nextLink")
        params = None


# ── 测试运行代码 ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("🔄 正在尝试连接 Microsoft Graph API...")
    try:
        # 1. 构建客户端，这步会自动读取 yaml 里的所有配置（包括 Secret）
        client = build_client()
        print(f"✅ 认证成功！获取到 Token。当前邮箱: {client.email}")

        # 2. 测试读取邮箱文件夹
        print("\n📂 正在读取收件箱文件夹...")
        folders = list_folders(client)
        if not folders:
            print("⚠️ 未找到子文件夹，或者收件箱为空。")
        else:
            for f in folders:
                print(f"   - 文件夹名: {f['displayName']} | 邮件数量: {f['totalItemCount']} | ID: {f['id']}")

        # 3. 测试拉取最新 5 条邮件
        print("\n📧 正在拉取收件箱最新的 5 条邮件...")
        messages = fetch_messages(client, folder="inbox", page_size=5)
        
        count = 0
        for msg in messages:
            count += 1
            subject = msg.get("subject", "无主题")
            sender = msg.get("from", {}).get("emailAddress", {}).get("address", "未知发件人")
            date = msg.get("receivedDateTime", "")
            has_attach = "📎 有附件" if msg.get("hasAttachments") else "无附件"
            
            print(f"[{count}] 时间: {date}")
            print(f"    发件人: {sender}")
            print(f"    主  题: {subject}")
            print(f"    状  态: {has_attach}\n")
            
            if count >= 5: 
                break

        print("🎉 测试完成！")

    except Exception as e:
        print(f"\n❌ 测试失败，发生错误: {e}")