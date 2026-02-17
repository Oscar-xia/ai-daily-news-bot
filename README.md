# AI Daily News Bot

[![CI](https://github.com/Oscar-xia/ai-daily-news-bot/actions/workflows/ci.yml/badge.svg)](https://github.com/Oscar-xia/ai-daily-news-bot/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Docker](https://img.shields.io/badge/docker-ready-brightgreen.svg)](https://hub.docker.com/)

**AI 驱动的技术日报自动生成系统**

自动采集 90+ 顶级技术博客，通过 AI 智能筛选、评分、摘要，每天生成精选技术日报并推送到邮箱。

---

## 功能亮点

- **多源采集** - RSS 订阅，覆盖 90+ 顶级技术博客
- **AI 处理** - 智能去重、相关性筛选、摘要生成、三维评分
- **日报生成** - Markdown 格式，含趋势分析和可视化图表
- **邮件推送** - 自动发送日报到指定邮箱
- **Web 管理** - 直观的管理界面，支持手动操作
- **Docker 支持** - 一键部署，开箱即用

## 快速开始

### 方式一：Docker（推荐）

```bash
# 1. 克隆项目
git clone https://github.com/Oscar-xia/ai-daily-news-bot.git
cd ai-daily-news-bot

# 2. 配置 API Key
cp .env.example .env
# 编辑 .env，填入 SILICONFLOW_API_KEY（从 https://cloud.siliconflow.cn/ 获取）

# 3. 一键启动
docker compose up -d

# 4. 访问管理界面
# http://localhost:8000
```

### 方式二：直接运行

```bash
# 1. 克隆项目
git clone https://github.com/Oscar-xia/ai-daily-news-bot.git
cd ai-daily-news-bot

# 2. 创建虚拟环境（推荐）
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 3. 安装依赖
pip install -r requirements.txt

# 4. 配置 API Key
cp .env.example .env
# 编辑 .env，填入 SILICONFLOW_API_KEY

# 5. 初始化并启动
python scripts/init_db.py
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### 验证安装

```bash
# 检查服务状态
curl http://localhost:8000/health

# 查看系统状态
python scripts/cli.py status
```

---

## 自动接收日报

编辑 `.env` 配置邮件：

```bash
EMAIL_ENABLED=true
EMAIL_SENDER=your_email@qq.com       # 发件邮箱
EMAIL_PASSWORD=授权码                 # 不是登录密码！
EMAIL_RECEIVERS=user@example.com     # 收件人

REPORT_GENERATION_HOUR=6             # 每天 6 点发送
```

启动后自动运行：
- 每 2 小时采集信息
- 每天 6 点生成日报并发邮件

---

## 常用命令

```bash
# 查看状态
python scripts/cli.py status

# 手动采集
python scripts/cli.py collect

# AI 处理
python scripts/cli.py process

# 生成日报
python scripts/cli.py generate

# 完整流程（采集 → 处理 → 生成）
python scripts/cli.py pipeline

# 发送测试邮件
python scripts/cli.py email --test
```

---

## 文档

| 文档 | 说明 |
|------|------|
| [配置详解](docs/CONFIG.md) | 环境变量、LLM 模型、邮件配置 |
| [架构设计](architecture.md) | 系统架构、数据模型 |
| [API 文档](http://localhost:8000/docs) | REST API 接口 |

---

## 项目结构

```
ai-daily-news-bot/
├── app/                 # 主应用
│   ├── collectors/      # 信息采集器
│   ├── processors/      # AI 处理器
│   ├── generators/      # 日报生成器
│   ├── llm/             # LLM 集成
│   └── api/             # REST API
├── frontend/            # Web 管理界面
├── scripts/             # 脚本工具
├── docs/                # 文档
├── Dockerfile
├── docker-compose.yml
└── requirements.txt
```

---

## 常见问题

<details>
<summary>如何添加自定义 RSS 源？</summary>

```bash
python scripts/cli.py source add -n "博客名称" -t rss -u "https://example.com/feed.xml"
```

在 Web 界面也可以添加：http://localhost:8000 → 信息源
</details>

<details>
<summary>日报为空？</summary>

```bash
# 检查数据
python scripts/cli.py status

# 降低阈值重新生成（默认 50 分，可降低）
python scripts/cli.py generate -m 20
```
</details>

<details>
<summary>依赖安装失败？</summary>

```bash
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```
</details>

---

## 贡献

欢迎 Issue 和 Pull Request！

1. Fork → 2. 分支 → 3. 提交 → 4. PR

---

## 致谢

本项目在开发过程中使用了以下工具和服务：

- [Claude Code](https://claude.ai/code) - AI 辅助编程
- [硅基流动](https://siliconflow.cn/) - LLM API 服务
- [RSSHub](https://github.com/DIYgod/RSSHub) - RSS 生成工具

---

## 许可证

[MIT License](LICENSE)
