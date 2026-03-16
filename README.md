# 🚀 企业投研邮件 AI 知识库 Skill (Active-Sync RAG)

这是一个为 AI Agent 打造的专业技能包。它集成了 **微软 Graph API**、**自动化文档解析**与 **ChromaDB 向量数据库**，实现了"邮件即知识"的闭环。

---

## 📂 目录结构说明

```text
.
├── README.md                # 本说明文件
├── SKILL.md                 # Agent 核心指令 (供大模型读取)
└── Bundled Resources/
    ├── scripts/             # 核心逻辑脚本
    │   ├── config.py       # 统一配置模块 (路径、常量、工具函数)
    │   ├── graph_client.py # Microsoft Graph API 客户端
    │   ├── step1_sync_engine.py   # 邮件增量同步
    │   ├── step2_parser.py        # 文档解析与分块
    │   ├── step3_vector_db.py     # 向量数据库更新
    │   └── email_knowledge_tool.py # 统一检索入口
    ├── references/          # 环境依赖 (requirements.txt)
    └── assets/             # 静态配置与持久化数据库
        ├── Download_EQD.yaml    # API 凭证配置
        ├── sync_state.json       # 同步状态记录
        └── knowledge_base/      # 知识库数据
            ├── raw_data/        # 原始邮件与附件
            ├── chroma_db/       # 向量数据库
            ├── new_chunks.json   # 新知识块临时文件
            └── processed_folders.json  # 已处理记录
```

---

## 🛠️ 第一次使用：环境配置指南

请按照以下步骤，在 **3 分钟内** 完成本地环境搭建：

### 1. 创建虚拟环境并安装依赖

在终端进入项目根目录，运行：

```bash
# 创建虚拟环境
python -m venv .venv

# 激活虚拟环境 (Mac/Linux)
source .venv/bin/activate
# 激活虚拟环境 (Windows)
# .venv\Scripts\activate

# 安装所有必要的库
pip install -r "Bundled Resources/references/requirements.txt"

```

### 2. 配置企业凭证

打开 `Bundled Resources/assets/Download_EQD.yaml`，填入从 Azure 门户获取的凭证：

* `tenant_id`: 微软租户 ID
* `client_id`: 应用程序 ID
* `client_secret`: 客户端密码
* `email`: 目标邮箱地址 (个人或共享邮箱)

---

## 🚀 运行与维护

该 Skill 采用 **即时增量同步 (Active-Sync)** 技术，主要有以下两种运行方式：

### 方式 A：Agent 自动调用 (推荐)

当 AI Agent 加载了 `SKILL.md` 并调用 `email_knowledge_tool.py` 时，系统会自动按以下流水线运行：

1. **检查更新**：对比时间戳，仅抓取新邮件（默认从30天前开始）
2. **增量解析**：仅解析新下载的 PDF/Excel
3. **追加向量**：仅将新知识块存入数据库
4. **语义检索**：返回最相关的结果

**⚠️ 注意**：默认使用增量同步模式，只会拉取新邮件。如需控制同步时间范围，请查看"方式三"部分。

### 方式 B：手动初始化/强制更新

如果你想在不启动 AI 的情况下手动刷新本地数据库，请依次运行：

```bash
cd "Bundled Resources/scripts"
python step1_sync_engine.py    # 同步邮件
python step2_parser.py         # 解析文档
python step3_vector_db.py      # 更新索引
```

---

## ✨ 主要改进 (v2.0)

### 高优先级优化
1. **统一配置管理** - 新增 `config.py` 模块，集中管理所有路径和常量
2. **完善的错误处理** - 所有关键操作都添加了异常捕获和容错机制
3. **合理的时间默认值** - 默认从30天前开始同步，而非未来的2026年
4. **安全的文件名处理** - 完整处理 Windows/Unix 非法字符，限制文件大小（50MB）
5. **健壮的断点续传** - 批量保存时间戳，避免单次失败影响整体进度

### 技术细节
- 使用 `pathlib` 进行跨平台路径管理
- 添加完整的类型注解，提高代码可维护性
- 支持多编码格式（UTF-8、GBK）的文本文件读取
- 批量插入优化，减少数据库 I/O 操作
- 详细的日志输出，便于问题排查

---

## ⚠️ 注意事项

* **网络权限**：确保你的网络环境可以访问 `graph.microsoft.com`
* **数据隐私**：`assets/knowledge_base` 存储在本地，不会上传至任何云端，确保了金融数据的私密性
* **首次运行**：第一次同步大量历史邮件时，解析过程可能较慢，请耐心等待
* **附件大小**：默认限制单个附件最大 50MB，可在 `config.py` 中调整
* **内存需求**：ChromaDB 需要一定的内存，建议至少 2GB 可用内存

---

## 🐛 常见问题

### Q: 同步失败怎么办？
A: 检查网络连接和凭证配置，查看错误日志。已同步的邮件会记录时间戳，不会重复处理。

### Q: 文件名乱码？
A: 已自动处理非法字符，如仍有问题请检查源邮件的编码格式。

### Q: 解析速度慢？
A: 增量模式下只会处理新邮件，首次同步可以分批次进行。

### Q: 数据库文件占用空间大？
A: ChromaDB 包含向量索引，属于正常现象。可以定期清理历史数据。
