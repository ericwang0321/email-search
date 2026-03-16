# Email & Research Knowledge Base - Active-Sync Search

## Trigger Conditions (触发条件) - 必须调用此 Skill

当用户 prompt 符合以下**任意**模式时，**必须立即**调用此 Skill:

### 1. Research 模式 (投研相关)
- 用户询问公司/行业/股票信息: "腾讯最近有什么消息?" "宁德时代业绩怎么样?"
- 用户索要研报/分析: "有没有关于AI行业的研报?" "找一下新能源的分析"
- 用户提到投资相关概念: "估值"、"财报"、"业绩"、"预披露"、"IPO"、"融资"
- 用户在做市场/行业研究: "帮我研究一下..." "分析一下..."
- 用户询问时间敏感信息: "最新"、"今天"、"最近"、"刚刚"、"这周"

### 2. Email 内容模式 (邮件相关问题)
- 用户直接提及邮件: "邮件里有没有..." "收到过关于...的邮件吗?"
- 用户询问特定内容来源: "有没有关于...的材料?" "查一下...的文档"
- 用户需要找历史记录: "之前收到的..." "上次那个..."
- 用户索要附件/文件: "PDF"、"Excel"、"报告"、"模型"

### 3. 知识库查询模式
- 用户要求搜索/检索: "搜一下..." "查一下..." "找找..."
- 用户需要信息汇总: "汇总一下..." "总结一下..."

---

## CRITICAL: Mandatory Pre-Sync Rule (强制预同步规则)

**⚠️ ABSOLUTE REQUIREMENT - 在执行任何其他操作之前:**

```
用户提问 → [第一步: 调用 search_email_knowledge_base] → [第二步: 基于返回结果回答]
```

**禁止跳过同步!** 此工具内置了实时同步机制:
- 调用 `search_email_knowledge_base(query)` 会**自动**执行:
  1. `run_incremental_sync()` - 拉取最新邮件
  2. `run_parser()` - 解析新内容
  3. `run_vector_db()` - 入库向量
  4. 最后才执行搜索

**你只需要调用一次函数，同步+搜索会自动完成。**

---

## 执行规范

### Query 构建策略
将用户模糊需求转化为精准关键词组合:
- 用户: "看看有没有云圣智能的新消息" → Query: `"云圣智能 最新 研报 邮件 进展"`
- 用户: "宁德时代最近业绩怎么样" → Query: `"宁德时代 业绩 财报 收入 利润"`
- 用户: "今天有什么重要邮件" → Query: `"重要 公告 通知 今日 最新"`

### 回复格式规范
**必须引用来源:**
- ✅ 正确: "根据 2024-03-13 收到的邮件《关于云圣智能Pre-IPO路演》中提到的内容..."
- ❌ 错误: "云圣智能正在准备IPO..." (无来源引用)

**无结果时:**
- 必须明确告知: "我已经检查了您的最新邮件(截至刚才同步)，目前没有发现关于 [关键词] 的相关信息。"

### 参数选择
- 默认 `top_k=3`
- 复杂问题可增加至 `top_k=5-10`
- 简单查证可减少至 `top_k=1-2`

---

## 错误处理
- 如果工具返回 `error`: 告知用户同步可能存在临时问题，并尝试基于本地历史数据回答
- 如果同步超时: 提示用户"正在获取最新邮件，请稍候"

---

## 执行入口

### 方式一：直接调用（推荐）
```bash
cd "C:/Users/ChinaAMC(HK)/.claude/skills/email-search"
.venv/Scripts/python "Bundled Resources/scripts/email_knowledge_tool.py" "搜索关键词" 3
```

### 方式二：命令行参数
```bash
.venv/Scripts/python "Bundled Resources/scripts/email_knowledge_tool.py" "宁德时代 业绩" 5
```

### 方式三：控制同步时间范围（新增功能）
```bash
# 同步过去7天的邮件
.venv/Scripts/python "Bundled Resources/scripts/email_knowledge_tool.py" "搜索关键词" 3 7

# 同步过去30天的邮件（默认）
.venv/Scripts/python "Bundled Resources/scripts/email_knowledge_tool.py" "搜索关键词" 3 30

# 同步过去3个月的邮件
.venv/Scripts/python "Bundled Resources/scripts/email_knowledge_tool.py" "搜索关键词" 3 90

# 同步过去1年的邮件
.venv/Scripts/python "Bundled Resources/scripts/email_knowledge_tool.py" "搜索关键词" 3 365

# 增量同步模式（只拉取新邮件）
.venv/Scripts/python "Bundled Resources/scripts/email_knowledge_tool.py" "搜索关键词" 3
```

**参数说明：**
- 第一个参数: 搜索关键词（必需）
- 第二个参数: 返回结果数量 top_k（可选，默认 3）
- 第三个参数（可选）: 同步时间范围（天数）
  - `7`: 同步过去7天
  - `30`: 同步过去30天（默认）
  - `90`: 同步过去3个月
  - `365`: 同步过去1年
  - `0`: 全量同步（重新开始，会删除所有已有数据，不推荐）
  - `None` 或省略: 增量同步模式（默认，只拉取新邮件）

---

## 新功能说明

### 📅 时间范围控制

为了避免同步多年的历史邮件，你可以指定 `sync_days` 参数来控制同步范围：

| sync_days | 效果 | 说明 |
|-----------|------|------|
| `None` 或省略 | 增量同步 | 只拉取新邮件（高效，推荐） |
| `7` | 过去7天 | 快速查看近期邮件 |
| `30` | 过去30天（默认） | 标准月度范围 |
| `90` | 过去3个月 | 季度或半年度分析 |
| `365` | 过去1年 | 年度范围分析 |
| `0` | 全量同步 | 重新开始（会删除已有数据，慎用） |

**示例使用**:
```bash
# 只查询最近30天的数据（不重新同步）
python "Bundled Resources/scripts/email_knowledge_tool.py" "搜索内容" 3 30

# 首次使用：同步过去3个月的数据
python "Bundled Resources/scripts/email_knowledge_tool.py" "搜索内容" 3 90
```

**注意事项**:
- ✅ 增量模式（sync_days=None）不会删除已有数据，只会追加新邮件
- ⚠️ 全量同步（sync_days=0）会清空知识库，首次初始化时使用
- 🔄 使用 sync_days=7/30/90 可以控制同步的历史范围，避免处理过多旧邮件


## 函数接口
- **函数:** `search_email_knowledge_base(query, top_k)`
- **位置:** `Bundled Resources/scripts/email_knowledge_tool.py`
