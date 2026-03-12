import os
import json
import pandas as pd
import pymupdf
from langchain_text_splitters import RecursiveCharacterTextSplitter

# 注意相对路径，指向上一级的 assets 目录
RAW_DATA_DIR = "../assets/knowledge_base/raw_data"
NEW_CHUNKS_FILE = "../assets/knowledge_base/new_chunks.json"
PROCESSED_RECORD = "../assets/knowledge_base/processed_folders.json"

text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=800,
    chunk_overlap=100,
    separators=["\n\n", "\n", "。", "！", "？", " ", ""]
)

def parse_pdf(file_path: str) -> str:
    text = ""
    try:
        doc = pymupdf.open(file_path)
        for page in doc:
            text += page.get_text() + "\n"
        doc.close()
    except Exception as e:
        print(f"⚠️ 读取 PDF 失败 {file_path}: {e}")
    return text

def parse_excel(file_path: str) -> str:
    text = ""
    try:
        excel_data = pd.read_excel(file_path, sheet_name=None)
        for sheet_name, df in excel_data.items():
            text += f"\n\n### Excel 表格名: {sheet_name}\n"
            text += df.fillna("").to_markdown(index=False) + "\n"
    except Exception as e:
        print(f"⚠️ 读取 Excel 失败 {file_path}: {e}")
    return text

def load_processed_folders() -> set:
    """读取已处理过的文件夹记忆本"""
    if os.path.exists(PROCESSED_RECORD):
        with open(PROCESSED_RECORD, "r", encoding="utf-8") as f:
            return set(json.load(f))
    return set()

def save_processed_folders(processed_set: set):
    """保存记忆本"""
    with open(PROCESSED_RECORD, "w", encoding="utf-8") as f:
        json.dump(list(processed_set), f, ensure_ascii=False, indent=2)

def run_parser():
    print("🧠 初始化增量文档解析引擎...")
    
    if not os.path.exists(RAW_DATA_DIR):
        print("❌ 找不到 raw_data 文件夹。请先运行 step1。")
        return

    # 1. 加载记忆本
    processed_folders = load_processed_folders()
    folders = [f for f in os.listdir(RAW_DATA_DIR) if os.path.isdir(os.path.join(RAW_DATA_DIR, f))]
    
    new_chunks = []
    newly_processed_count = 0
    
    for folder_name in folders:
        # 2. 核心：如果这个文件夹已经解析过，直接跳过！极大地节省时间
        if folder_name in processed_folders:
            continue
            
        folder_path = os.path.join(RAW_DATA_DIR, folder_name)
        parts = folder_name.split("_", 1)
        email_date = parts[0] if len(parts) > 1 else "Unknown Date"
        email_subject = parts[1] if len(parts) > 1 else folder_name
        
        print(f"  📄 发现新数据，正在解析: {folder_name[:40]}...")
        
        for file_name in os.listdir(folder_path):
            file_path = os.path.join(folder_path, file_name)
            content = ""
            
            if file_name.endswith(".txt"):
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()
            elif file_name.lower().endswith(".pdf"):
                content = parse_pdf(file_path)
            elif file_name.lower().endswith((".xlsx", ".xls")):
                content = parse_excel(file_path)
                
            if not content.strip():
                continue
                
            chunks = text_splitter.split_text(content)
            for i, chunk_text in enumerate(chunks):
                new_chunks.append({
                    "source_email_date": email_date,
                    "source_email_subject": email_subject,
                    "source_file": file_name,
                    "chunk_index": i,
                    "content": chunk_text
                })

        # 解析完一个文件夹，把它加入记忆本
        processed_folders.add(folder_name)
        newly_processed_count += 1

    # 3. 如果没有新数据，清理战场并退出
    if newly_processed_count == 0:
        print("✅ 没有需要解析的新文件夹，数据已是最新的。")
        if os.path.exists(NEW_CHUNKS_FILE):
            os.remove(NEW_CHUNKS_FILE)
        return

    # 4. 将提取出的“新数据”存入专属文件，专供 step 3 使用
    with open(NEW_CHUNKS_FILE, "w", encoding="utf-8") as f:
        json.dump(new_chunks, f, ensure_ascii=False, indent=2)
        
    save_processed_folders(processed_folders)
    print(f"\n🎉 增量解析完成！新增处理了 {newly_processed_count} 个文件夹，生成了 {len(new_chunks)} 个新知识块。")

if __name__ == "__main__":
    run_parser()