import json
import os
import hashlib
import chromadb
from typing import List, Dict, Any

from config import (
    NEW_CHUNKS_FILE,
    CHROMA_DB_DIR,
    COLLECTION_NAME,
    BATCH_SIZE,
)


def load_new_chunks() -> List[Dict[str, Any]]:
    """
    加载新知识块文件
    返回: 知识块列表，文件不存在或为空时返回空列表
    """
    if not os.path.exists(NEW_CHUNKS_FILE):
        return []

    try:
        with open(NEW_CHUNKS_FILE, "r", encoding="utf-8") as f:
            chunks = json.load(f)
            return chunks if chunks else []
    except (json.JSONDecodeError, IOError) as e:
        print(f"⚠️ 读取新知识块文件失败: {e}")
        return []


def prepare_batch_data(chunks: List[Dict[str, Any]]) -> tuple:
    """
    准备批量插入的数据
    返回: (documents, metadatas, ids)
    """
    documents = []
    metadatas = []
    ids = []

    for chunk in chunks:
        documents.append(chunk["content"])
        metadatas.append({
            "source_email_date": chunk.get("source_email_date", "Unknown"),
            "source_email_subject": chunk.get("source_email_subject", "Unknown"),
            "source_file": chunk.get("source_file", "Unknown"),
        })
        # 确保唯一性，防止覆盖其他数据
        # 加入邮件主题 hash 确保同一天多封邮件的同名附件不会产生重复 ID
        subject = chunk.get('source_email_subject', 'unknown')
        subject_hash = hashlib.md5(subject.encode()).hexdigest()[:8]
        chunk_id = f"{chunk.get('source_email_date', 'unknown')}_{subject_hash}_{chunk.get('source_file', 'unknown')}_{chunk.get('chunk_index', 0)}"
        ids.append(chunk_id)

    return documents, metadatas, ids


def run_vector_db() -> int:
    """
    运行增量向量数据库更新
    返回: 成功插入的知识块数量
    """
    print("🗄️ 初始化增量向量数据库...")

    # 加载新知识块
    chunks = load_new_chunks()

    if not chunks:
        print("✅ 未发现新知识块，数据库无需更新。")
        return 0

    print(f"📦 成功加载 {len(chunks)} 个新知识块，准备追加灌入 ChromaDB...")

    try:
        # 连接数据库
        client = chromadb.PersistentClient(path=str(CHROMA_DB_DIR))
        collection = client.get_or_create_collection(name=COLLECTION_NAME)

        existing_count = collection.count()
        print(f"ℹ️ 当前数据库中已有 {existing_count} 条历史数据。")

        # 准备批量数据
        documents, metadatas, ids = prepare_batch_data(chunks)

        # 批量插入
        total_inserted = 0
        for i in range(0, len(documents), BATCH_SIZE):
            end = min(i + BATCH_SIZE, len(documents))
            print(f"  ⏳ 正在追加插入第 {i+1} 到 {end} 个新知识块...")

            try:
                collection.upsert(
                    documents=documents[i:end],
                    metadatas=metadatas[i:end],
                    ids=ids[i:end]
                )
                total_inserted += (end - i)
            except Exception as e:
                print(f"     ⚠️ 批次 {i+1}-{end} 插入失败: {e}")
                continue

        print(f"\n🎉 增量更新完成！数据库最新总数据量: {collection.count()} 条。")
        print(f"   本批次成功插入: {total_inserted} 个知识块")

        # 清理临时文件
        try:
            os.remove(NEW_CHUNKS_FILE)
        except OSError as e:
            print(f"⚠️ 删除临时文件失败: {e}")

        return total_inserted

    except Exception as e:
        print(f"❌ 数据库更新失败: {e}")
        return 0


if __name__ == "__main__":
    run_vector_db()
