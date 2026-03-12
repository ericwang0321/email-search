# 🚀 企业投研邮件 AI 知识库 Skill (Active-Sync RAG)

这是一个为 AI Agent 打造的专业技能包。它集成了 **微软 Graph API**、**自动化文档解析**与 **ChromaDB 向量数据库**，实现了“邮件即知识”的闭环。

---

## 📂 目录结构说明

```text
.
├── README.md                # 本说明文件
├── SKILL.md                 # Agent 核心指令 (供大模型读取)
└── Bundled Resources/
    ├── scripts/             # 核心逻辑脚本 (同步、解析、入库、工具接口)
    ├── references/          # 环境依赖 (requirements.txt)
    └── assets/              # 静态配置与持久化数据库 (YAML、JSON、DB)

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

1. **检查更新**：对比时间戳，仅抓取新邮件。
2. **增量解析**：仅解析新下载的 PDF/Excel。
3. **追加向量**：仅将新知识块存入数据库。
4. **语义检索**：返回最相关的结果。

### 方式 B：手动初始化/强制更新

如果你想在不启动 AI 的情况下手动刷新本地数据库，请依次运行：

```bash
cd "Bundled Resources/scripts"
python step1_sync_engine.py    # 同步邮件
python step2_parser.py         # 解析文档
python step3_vector_db.py      # 更新索引

```

---

## ⚠️ 注意事项

* **网络权限**：确保你的网络环境可以访问 `graph.microsoft.com`。
* **数据隐私**：`assets/knowledge_base` 存储在本地，不会上传至任何云端，确保了金融数据的私密性。
* **首次运行**：第一次同步大量历史邮件时，解析过程可能较慢，请耐心等待。