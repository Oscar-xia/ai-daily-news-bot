# AI Daily News Bot - Project Instructions

## Project Context

AI + 投资 + Web3 每日早报自动生成系统。

**核心流程**: 信息采集 → AI 筛选处理 → 人工审核 → 生成早报

> 详细项目需求见 architecture.md 和 task.json

---

## MANDATORY: Agent Workflow

Every new agent session MUST follow this workflow:

### Step 1: Initialize Environment

```bash
./init.sh
```

This will:
- Create Python virtual environment
- Install all dependencies
- Create necessary directories (data/, output/, logs/)

**DO NOT skip this step.**

### Step 2: Select Next Task

Read `task.json` and select ONE task to work on.

Selection criteria (in order of priority):
1. Choose a task where `passes: false`
2. Consider dependencies - fundamental features should be done first
3. Pick the lowest ID incomplete task (tasks are ordered by dependency)

### Step 3: Implement the Task

- Read the task description and steps carefully
- Read `architecture.md` for design details
- Implement the functionality to satisfy all steps
- Follow existing code patterns and conventions

### Step 4: Test Thoroughly

After implementation, verify ALL steps in the task:

**测试要求（Testing Requirements - MANDATORY）：**

1. **Python 代码测试**：
   - 使用 `python -m pytest tests/` 运行单元测试
   - 或手动测试功能是否正常

2. **模块测试**：
   - 采集器：运行 `python scripts/run_collector.py` 验证采集功能
   - 处理器：运行 `python scripts/run_processor.py` 验证 AI 处理
   - 生成器：运行 `python scripts/run_generator.py` 验证早报生成

3. **API 测试**（如果涉及 API）：
   - 启动服务 `uvicorn app.main:app --reload`
   - 使用 curl 或浏览器测试端点

**测试清单：**
- [ ] 代码没有语法错误
- [ ] 模块可以正常导入
- [ ] 功能按预期工作
- [ ] 边界情况处理正确

### Step 5: Update Progress

Write your work to `progress.txt`:

```
## [Date] - Task: [task description]

### What was done:
- [specific changes made]

### Testing:
- [how it was tested]

### Notes:
- [any relevant notes for future agents]
```

### Step 6: Commit Changes (包含 task.json 更新)

**IMPORTANT: 所有更改必须在同一个 commit 中提交，包括 task.json 的更新！**

流程：
1. 更新 `task.json`，将任务的 `passes` 从 `false` 改为 `true`
2. 更新 `progress.txt` 记录工作内容
3. 一次性提交所有更改：

```bash
git add .
git commit -m "[task description] - completed"
```

**规则:**
- 只有在所有步骤都验证通过后才标记 `passes: true`
- 永远不要删除或修改任务描述
- 永远不要从列表中移除任务
- **一个 task 的所有内容（代码、progress.txt、task.json）必须在同一个 commit 中提交**

---

## ⚠️ 阻塞处理（Blocking Issues）

**如果任务无法完成测试或需要人工介入，必须遵循以下规则：**

### 需要停止任务并请求人工帮助的情况：

1. **缺少环境配置**：
   - .env 需要填写真实的 API 密钥
   - 需要开通 LLM API (OpenAI/智谱/通义)
   - 需要 Tavily API Key
   - 需要配置 RSSHub

2. **外部依赖不可用**：
   - LLM API 服务不可用
   - RSS 源无法访问
   - Twitter 采集被限制

3. **测试无法进行**：
   - 需要真实 API 调用但无密钥
   - 依赖外部服务尚未配置

### 阻塞时的正确操作：

**DO NOT（禁止）：**
- ❌ 提交 git commit
- ❌ 将 task.json 的 passes 设为 true
- ❌ 假装任务已完成

**DO（必须）：**
- ✅ 在 progress.txt 中记录当前进度和阻塞原因
- ✅ 输出清晰的阻塞信息，说明需要人工做什么
- ✅ 停止任务，等待人工介入

### 阻塞信息格式：

```
🚫 任务阻塞 - 需要人工介入

**当前任务**: [任务名称]

**已完成的工作**:
- [已完成的代码/配置]

**阻塞原因**:
- [具体说明为什么无法继续]

**需要人工帮助**:
1. [具体的步骤 1]
2. [具体的步骤 2]
...

**解除阻塞后**:
- 运行 [命令] 继续任务
```

---

## Project Structure

```
/
├── CLAUDE.md              # This file - workflow instructions
├── architecture.md        # Architecture design document
├── task.json              # Task definitions (source of truth)
├── progress.txt           # Progress log from each session
├── init.sh                # Initialization script
├── requirements.txt       # Python dependencies
├── .env.example           # Environment variables template
│
├── app/                   # Main application
│   ├── __init__.py
│   ├── main.py            # FastAPI entry point
│   ├── config.py          # Configuration management
│   ├── database.py        # Database connection
│   ├── scheduler.py       # APScheduler config
│   │
│   ├── collectors/        # Information collectors
│   │   ├── base.py
│   │   ├── rss_collector.py
│   │   ├── twitter_collector.py
│   │   └── search_collector.py
│   │
│   ├── processors/        # AI processing modules
│   │   ├── deduplicator.py
│   │   ├── filter.py
│   │   ├── summarizer.py
│   │   ├── classifier.py
│   │   └── scorer.py
│   │
│   ├── generators/        # Report generators
│   │   └── report_generator.py
│   │
│   ├── llm/               # LLM integration
│   │   ├── base.py
│   │   └── prompts.py
│   │
│   ├── models/            # Data models
│   │   └── schemas.py
│   │
│   └── api/               # API routes
│       └── routes.py
│
├── scripts/               # Utility scripts
│   ├── init_db.py
│   ├── run_collector.py
│   ├── run_processor.py
│   ├── run_generator.py
│   └── cli.py
│
├── data/                  # Database files
│   └── news.db
│
├── output/                # Generated reports
│   └── reports/
│
├── logs/                  # Log files
│
└── tests/                 # Unit tests
```

## Commands

```bash
# Environment setup
source venv/bin/activate    # Activate virtual environment
./init.sh                   # Initialize project

# Database
python scripts/init_db.py   # Initialize database

# Core operations
python scripts/run_collector.py   # Run information collection
python scripts/run_processor.py   # Run AI processing
python scripts/run_generator.py   # Generate daily report

# API server
uvicorn app.main:app --reload     # Start API server

# CLI tool
python scripts/cli.py --help      # Show CLI help
```

## Coding Conventions

- Python 3.11+
- Use type hints for all functions
- Use Pydantic for data validation
- Follow PEP 8 style guide
- Write docstrings for classes and functions
- Use async/await for I/O operations

---

## Key Rules

1. **One task per session** - Focus on completing one task well
2. **Test before marking complete** - All steps must pass
3. **Read architecture.md first** - Understand the design before implementing
4. **Document in progress.txt** - Help future agents understand your work
5. **One commit per task** - 所有更改（代码、progress.txt、task.json）必须在同一个 commit 中提交
6. **Never remove tasks** - Only flip `passes: false` to `true`
7. **Stop if blocked** - 需要人工介入时，不要提交，输出阻塞信息并停止
