#!/usr/bin/env python3
"""
邮件知识库搜索工具
使用方法: .venv/bin/python email_knowledge_tool.py "搜索关键词" [top_k]
"""
import sys
import os
from pathlib import Path

# 确保脚本目录在 Python 路径中
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import json
import io
import contextlib
import chromadb
from typing import Dict, Any, List

from step1_sync_engine import run_incremental_sync
from step2_parser import run_parser
from step3_vector_db import run_vector_db
from config import CHROMA_DB_DIR, COLLECTION_NAME


def search_email_knowledge_base(query: str, top_k: int = 3) -> str:
    """
    检索企业邮箱与投研知识库的工具 (Tool/Skill)。
    【特性】此工具自带"即时同步"功能。每次被调用时，它会先自动去邮箱拉取自上次同步以来的最新邮件和研报，解析并入库后，再执行精准检索。

    参数:
    - query (str): 提炼出的核心搜索关键词或自然语言问题，例如 "云圣智能Pre-IPO材料"、"宁德时代业绩" 或 "中东局势对油价的影响"。
    - top_k (int): 返回的最相关的知识块数量，默认为 3。如果问题较复杂，大模型可以自行决定增加此数值。

    返回:
    - str: 包含相关邮件内容及来源信息的 JSON 格式字符串，供大模型阅读和提取事实以回答用户。
    """

    # ==========================================================
    # 阶段一：即时增量更新 (Active Update Pipeline)
    # ==========================================================
    try:
        # 使用 StringIO 拦截标准输出，防止底层的 print 语句污染返回给 Agent 的 JSON 数据流
        f = io.StringIO()
        with contextlib.redirect_stdout(f):
            run_incremental_sync()  # 去邮箱看有没有新邮件
            run_parser()            # 有的话就解析成 Chunk
            run_vector_db()         # 把新 Chunk 追加进向量库

        # 如果你想在后台看日志排错，可以把下面这行取消注释，它会打印更新过程
        # print(f.getvalue())

    except Exception as e:
        # 如果增量更新因为网络等问题失败，不阻断程序，直接使用现有的本地数据库进行检索
        print(f"[Warning] 知识库即时增量同步失败，将使用现有本地数据进行检索: {e}")

    # ==========================================================
    # 阶段二：向量语义检索 (Vector Semantic Search)
    # ==========================================================
    try:
        # 连接本地 ChromaDB
        client = chromadb.PersistentClient(path=str(CHROMA_DB_DIR))
        collection = client.get_collection(name=COLLECTION_NAME)

        # 执行向量相似度检索
        results = collection.query(
            query_texts=[query],
            n_results=top_k
        )

        # 组装成大模型最容易理解和解析的 JSON 结构
        context_list = []
        if results and results.get('documents') and results['documents'][0]:
            docs = results['documents'][0]
            metas = results['metadatas'][0]

            for i in range(len(docs)):
                context_list.append({
                    "source_file": metas[i].get("source_file", "Unknown"),
                    "email_subject": metas[i].get("source_email_subject", "Unknown"),
                    "email_date": metas[i].get("source_email_date", "Unknown"),
                    "content_snippet": docs[i]
                })

        # 返回 JSON 字符串，大模型接收到后会将其作为 Context 进行回答合成
        return json.dumps(context_list, ensure_ascii=False, indent=2)

    except Exception as e:
        return json.dumps({"error": f"检索知识库时发生内部错误: {str(e)}"}, ensure_ascii=False)


# =====================================================================
# 下方为测试代码，可直接运行此文件测试整个前后台链路是否通畅
# =====================================================================
if __name__ == "__main__":
    # 支持命令行参数
    if len(sys.argv) >= 2:
        query = sys.argv[1]
        top_k = int(sys.argv[2]) if len(sys.argv) >= 3 else 3
    else:
        query = "宁德时代业绩超预期"  # 默认测试查询
        top_k = 3

    print(f"🚀 模拟大模型发起查询...")
    print(f"🔍 搜索关键词: {query}")
    print(f"📊 返回数量: {top_k}")
    print("⏳ 正在执行即时同步与检索...")

    tool_output = search_email_knowledge_base(query=query, top_k=top_k)

    print("\n✅ Tool 返回的最终 JSON 数据:")
    print(tool_output)
