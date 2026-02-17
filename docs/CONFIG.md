# 配置详解

本文档详细说明 AI Daily News Bot 的所有配置项。

## 快速配置

复制模板并编辑：

```bash
cp .env.example .env
```

**只需配置一个必填项即可运行**：

```bash
SILICONFLOW_API_KEY=your-api-key  # 从 https://cloud.siliconflow.cn/ 获取
```

---

## LLM 配置

本项目使用 [硅基流动](https://cloud.siliconflow.cn/) 作为 LLM 提供商。

```bash
LLM_PROVIDER=siliconflow
SILICONFLOW_API_KEY=your-api-key
SILICONFLOW_BASE_URL=https://api.siliconflow.cn/v1
SILICONFLOW_MODEL=Qwen/Qwen3-30B-A3B-Instruct-2507
```

### 获取 API Key

1. 访问 https://cloud.siliconflow.cn/
2. 注册并登录
3. 点击「API 密钥」→「创建新密钥」
4. 复制密钥到 `.env`

### 推荐模型

| 模型 | 说明 | 价格 |
|------|------|------|
| `Qwen/Qwen3-30B-A3B-Instruct-2507` | **推荐**，性价比高 | ¥0.7/¥2.8 /百万token |
| `deepseek-ai/DeepSeek-V3.2` | 旗舰模型 | ¥2/¥3 /百万token |
| `deepseek-ai/DeepSeek-R1-0528-Qwen3-8B` | **免费**，适合测试 | 免费 |

---

## 邮件配置

配置后可自动推送日报到邮箱。

```bash
EMAIL_ENABLED=true
EMAIL_SENDER=your_email@qq.com      # 发件邮箱
EMAIL_PASSWORD=xxxxxxxxxxxx         # 授权码，不是登录密码！
EMAIL_RECEIVERS=user@example.com    # 收件人（多个用逗号分隔）
```

### 获取授权码

| 邮箱 | 获取方式 |
|------|----------|
| QQ邮箱 | 设置 → 账户 → POP3/SMTP → 生成授权码 |
| 163邮箱 | 设置 → POP3/SMTP → 获取授权码 |
| Gmail | 账户 → 安全性 → 两步验证 → 应用密码 |

### 支持的邮箱

自动识别 SMTP 配置：QQ、163、126、Gmail、Outlook、阿里云、139 等。

---

## 调度器配置

```bash
SCHEDULER_ENABLED=true              # 启用定时任务
COLLECT_INTERVAL_HOURS=2            # 采集间隔（小时）
REPORT_GENERATION_HOUR=6            # 日报生成时间
```

运行逻辑：
- 每 N 小时：采集信息
- 每天指定时间：采集 + 处理 + 生成日报 + 发邮件

---

## 筛选配置

```bash
# 日报配置
REPORT_MIN_SCORE=15                 # 最低评分（3-30分制）
REPORT_TOP_N=15                     # 日报最大文章数

# 处理配置
PROCESS_BATCH_SIZE=20               # AI 处理批次大小
PROCESS_HOURS=24                    # 处理时间窗口（小时）
```

### 评分说明

每篇文章三维评分（各 1-10 分，总分 3-30）：

| 维度 | 说明 |
|------|------|
| 相关性 | 对 AI 从业者的价值 |
| 质量 | 内容深度和原创性 |
| 时效性 | 当前阅读价值 |

---

## 信息源配置

### 添加自定义 RSS 源

```bash
python scripts/cli.py source add -n "博客名称" -t rss -u "https://example.com/feed.xml"
```

### 管理信息源

```bash
# 列出所有源
python scripts/cli.py source list

# 禁用某个源
python scripts/cli.py source disable <ID>
```

---

## 完整配置示例

```bash
# === 必需 ===
SILICONFLOW_API_KEY=sk-xxxx

# === 可选 ===
SILICONFLOW_MODEL=Qwen/Qwen3-30B-A3B-Instruct-2507

SCHEDULER_ENABLED=true
COLLECT_INTERVAL_HOURS=2
REPORT_GENERATION_HOUR=6

EMAIL_ENABLED=true
EMAIL_SENDER=your@qq.com
EMAIL_PASSWORD=授权码
EMAIL_RECEIVERS=user@example.com

LOG_LEVEL=INFO
```
