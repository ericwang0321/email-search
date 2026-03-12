import json
import os
import chromadb

# 注意相对路径
NEW_CHUNKS_FILE = "../assets/knowledge_base/new_chunks.json"
DB_DIR = "../assets/knowledge_base/chroma_db"

def run_vector_db():
    print("🗄️ 初始化增量向量数据库...")
    
    # 1. 只寻找 step 2 吐出来的“新数据”
    if not os.path.exists(NEW_CHUNKS_FILE):
        print("✅ 未发现新知识块文件 (new_chunks.json)，数据库无需更新。")
        return
        
    with open(NEW_CHUNKS_FILE, "r", encoding="utf-8") as f:
        chunks = json.load(f)
        
    if not chunks:
        print("✅ 新知识块列表为空，数据库无需更新。")
        return
        
    print(f"📦 成功加载 {len(chunks)} 个新知识块，准备追加灌入 ChromaDB...")
    
    client = chromadb.PersistentClient(path=DB_DIR)
    collection = client.get_or_create_collection(name="email_knowledge_base")
    
    existing_count = collection.count()
    print(f"ℹ️ 当前数据库中已有 {existing_count} 条历史数据。")
    
    documents = []
    metadatas = []
    ids = []
    
    for chunk in chunks:
        documents.append(chunk["content"])
        metadatas.append({
            "source_email_date": chunk["source_email_date"],
            "source_email_subject": chunk["source_email_subject"],
            "source_file": chunk["source_file"],
        })
        # 确保 ID 具备唯一性，防止覆盖其他数据
        ids.append(f"{chunk['source_email_date']}_{chunk['source_file']}_{chunk['chunk_index']}")
        
    # 2. ⚠️ 核心改变：使用 upsert (追加或更新) 代替清空重写
    batch_size = 500
    for i in range(0, len(documents), batch_size):
        end = min(i + batch_size, len(documents))
        print(f"  ⏳ 正在追加插入第 {i+1} 到 {end} 个新知识块...")
        collection.upsert(
            documents=documents[i:end],
            metadatas=metadatas[i:end],
            ids=ids[i:end]
        )
        
    print(f"\n🎉 增量更新完成！数据库最新总数据量: {collection.count()} 条。")
    
    # 3. 阅后即焚：把这个临时的新数据文件删掉，免得下次运行又重复灌入
    os.remove(NEW_CHUNKS_FILE)

if __name__ == "__main__":
    run_vector_db()