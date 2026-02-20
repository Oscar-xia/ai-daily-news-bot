"""
Prompt templates for AI Daily News Bot.
Version 2.0 - 基于 ai-daily-digest 的三维评分体系
"""

from typing import List, Optional
import json


# =============================================================================
# 评分 + 分类 + 关键词（合并为一次调用）
# =============================================================================

SYSTEM_PROMPT_SCORING = """你是 AI 技术日报的内容策展人，负责筛选高质量的技术内容。

## 评分任务

对每篇文章进行三个维度的评分（1-10），同时完成分类和关键词提取。

## 评分维度

### 相关性 (relevance) - 对 AI 技术从业者的价值
- 10: 所有 AI 从业者必须知道的重大突破
- 7-9: 对大部分从业者有价值
- 4-6: 对特定领域有价值
- 1-3: 与 AI 技术关联不大

### 质量 (quality) - 内容深度和原创性
- 10: 深度原创，突破性洞见
- 7-9: 独特视角，分析深入
- 4-6: 信息准确，表达清晰
- 1-3: 内容浅或营销感强

### 时效性 (timeliness) - 当前阅读价值
- 10: 24小时内发布的重大消息
- 7-9: 近期重要进展（一周内）
- 4-6: 常青内容
- 1-3: 内容过时

## 分类（必须从以下选一个）

- ai-ml: AI、机器学习、LLM、深度学习
- security: 安全、隐私、漏洞、加密
- engineering: 软件工程、架构、编程语言、系统设计
- tools: 开发工具、开源项目、新库/框架
- opinion: 行业观点、个人思考、职业发展
- other: 其他

## 关键词

提取 2-4 个最能代表文章主题的关键词（英文，简短）"""


def get_scoring_prompt(articles: List[dict]) -> str:
    """Generate prompt for scoring multiple articles.

    Args:
        articles: List of dicts with index, title, description, sourceName
    """
    articles_list = "\n\n---\n\n".join([
        f"Index {a['index']}: [{a.get('sourceName', 'Unknown')}] {a['title']}\n{a.get('description', '')[:300]}"
        for a in articles
    ])

    return f"""{SYSTEM_PROMPT_SCORING}

## 待评分文章

{articles_list}

## 输出格式（严格 JSON，无 markdown 代码块）

{{
  "results": [
    {{
      "index": 0,
      "relevance": 8,
      "quality": 7,
      "timeliness": 9,
      "category": "ai-ml",
      "keywords": ["GPT-4", "multimodal", "benchmark"]
    }}
  ]
}}"""


# =============================================================================
# 摘要 + 中文标题 + 推荐理由
# =============================================================================

SYSTEM_PROMPT_SUMMARY = """你是技术内容摘要专家。请为文章完成三件事：

1. **中文标题** (titleZh): 将英文标题翻译成自然的中文。如果原标题是中文则保持不变。

2. **摘要** (summary): 4-6 句话的结构化摘要
   - 核心问题/主题（1句）
   - 关键论点/方案/发现（2-3句）
   - 结论/核心观点（1句）
   要求：
   - 直接说重点，不用"本文讨论了"开头
   - 包含具体技术名词、数据、方案名称
   - 保留关键数字（性能提升%、用户数、版本号等）
   - 读者 30 秒读完摘要就能决定是否读原文

3. **推荐理由** (reason): 1 句话说明为什么值得读，区别于摘要

用中文回答。"""


def get_summary_prompt(title: str, content: str, source: str = "") -> str:
    """Generate prompt for summarizing an article."""
    source_info = f"\n来源: {source}" if source else ""

    return f"""{SYSTEM_PROMPT_SUMMARY}

## 文章

标题: {title}
{source_info}

内容:
{content[:2000] if content else '（无内容）'}

## 输出格式（严格 JSON）

{{
  "titleZh": "中文标题",
  "summary": "摘要内容...",
  "reason": "推荐理由..."
}}"""


# =============================================================================
# 简化版摘要（仅标题+一句话简介，用于未入选文章）
# =============================================================================

SYSTEM_PROMPT_BRIEF = """你是技术内容摘要专家。请为文章生成：

1. **中文标题** (titleZh): 将英文标题翻译成自然的中文
2. **一句话简介** (brief): 用1句话（20-40字）概括文章核心内容

要求：
- 简介要包含具体的技术名词或关键信息
- 直接说重点，不用"本文介绍了"开头
- 用中文回答"""


def get_brief_prompt(title: str, content: str) -> str:
    """Generate prompt for brief summary (title + one sentence)."""
    return f"""{SYSTEM_PROMPT_BRIEF}

## 文章

标题: {title}

内容:
{content[:1000] if content else '（无内容）'}

## 输出格式（严格 JSON）

{{
  "titleZh": "中文标题",
  "brief": "一句话简介..."
}}"""


def parse_brief_response(response: str) -> dict:
    """Parse brief summary response from LLM.

    Returns:
        Dict with title_zh, brief
    """
    import re

    response = response.strip()

    # Strip markdown code blocks if present
    if response.startswith('```'):
        response = re.sub(r'^```(?:json)?\n?', '', response)
        response = re.sub(r'\n?```$', '', response)

    try:
        data = json.loads(response)
        return {
            'title_zh': data.get('titleZh', ''),
            'brief': data.get('brief', ''),
        }
    except json.JSONDecodeError:
        return {
            'title_zh': '',
            'brief': '',
        }


# =============================================================================
# 趋势总结（今日看点）
# =============================================================================

SYSTEM_PROMPT_HIGHLIGHTS = """你是技术趋势分析师。根据今日精选文章，归纳技术圈的主要趋势。"""


def get_highlights_prompt(articles: List[dict]) -> str:
    """Generate prompt for creating today's highlights.

    Args:
        articles: List of dicts with title_zh/title, summary, category
    """
    article_list = "\n".join([
        f"{i+1}. [{a.get('category', 'other')}] {a.get('title_zh') or a.get('title', '')} — {(a.get('summary') or '')[:100]}"
        for i, a in enumerate(articles[:15])
    ])

    return f"""{SYSTEM_PROMPT_HIGHLIGHTS}

根据以下今日精选技术文章，写一段 3-5 句话的"今日看点"总结。

要求：
- 提炼 2-3 个主要技术趋势或话题
- 不要逐篇列举，要做宏观归纳
- 风格简洁有力，像新闻导语
- 用中文回答

文章列表：
{article_list}

直接返回纯文本总结，不要 JSON，不要 markdown 格式。"""


# =============================================================================
# 响应解析函数
# =============================================================================

def parse_scoring_response(response: str) -> List[dict]:
    """Parse scoring response from LLM.

    Returns:
        List of dicts with index, relevance, quality, timeliness, category, keywords
    """
    import re

    response = response.strip()

    # Strip markdown code blocks if present
    if response.startswith('```'):
        response = re.sub(r'^```(?:json)?\n?', '', response)
        response = re.sub(r'\n?```$', '', response)

    try:
        data = json.loads(response)
        results = []

        for item in data.get('results', []):
            # Clamp scores to 1-10
            def clamp(v):
                return min(10, max(1, int(v))) if isinstance(v, (int, float)) else 5

            results.append({
                'index': item.get('index', 0),
                'relevance': clamp(item.get('relevance', 5)),
                'quality': clamp(item.get('quality', 5)),
                'timeliness': clamp(item.get('timeliness', 5)),
                'category': item.get('category', 'other') if item.get('category') in [
                    'ai-ml', 'security', 'engineering', 'tools', 'opinion', 'other'
                ] else 'other',
                'keywords': item.get('keywords', [])[:4] if isinstance(item.get('keywords'), list) else [],
            })

        return results

    except json.JSONDecodeError:
        return []


def parse_summary_response(response: str) -> dict:
    """Parse summary response from LLM.

    Returns:
        Dict with titleZh, summary, reason
    """
    import re

    response = response.strip()

    # Strip markdown code blocks if present
    if response.startswith('```'):
        response = re.sub(r'^```(?:json)?\n?', '', response)
        response = re.sub(r'\n?```$', '', response)

    try:
        data = json.loads(response)
        return {
            'title_zh': data.get('titleZh', ''),
            'summary': data.get('summary', ''),
            'reason': data.get('reason', ''),
        }
    except json.JSONDecodeError:
        return {
            'title_zh': '',
            'summary': response[:200] if response else '',
            'reason': '',
        }


# =============================================================================
# 今日启示（技术风向 / 深度思考 / 变现机会）
# =============================================================================

SYSTEM_PROMPT_INSIGHTS = """你是一位资深技术投资人 + 连续创业者，同时深谙技术趋势。

你的任务是基于今日技术文章，写出真正有见地的"启示"——不是泛泛而谈的空话，而是能让读者拍案叫绝的独特洞察。

## 核心原则

1. **反直觉**：大多数人看不到的角度，你说出来
2. **可行动**：读者看完知道下一步该做什么
3. **有锋芒**：可以有争议性观点，比平庸好一万倍
4. **讲人话**：不用"赋能"、"闭环"、"底层逻辑"这类废话

## 输出风格示例

❌ 差（空话）：
"AI 发展迅速，建议关注相关技术，把握投资机会。"

✅ 好（有洞见）：
"所有人都在卷 Agent 编排，但真正赚钱的是 Agent 的'审计层'——谁能证明 AI 的决策是可信的，谁就掌握了企业市场的入场券。"

❌ 差（泛泛）：
"建议学习 Python 和机器学习基础知识。"

✅ 好（具体且有反直觉）：
"与其学怎么写 Prompt，不如学怎么设计'Human-in-the-loop'的决策节点——这是未来 3 年最稀缺的能力，因为纯 AI 方案在合规行业根本过不了审计。"
"""


def get_insights_prompt(articles: List[dict]) -> str:
    """Generate prompt for creating daily insights.

    Args:
        articles: List of dicts with title_zh/title, summary, category, keywords
    """
    # 构建文章摘要列表
    article_list = []
    for i, a in enumerate(articles[:15]):
        title = a.get('title_zh') or a.get('title', '')
        summary = (a.get('summary') or '')[:150]
        category = a.get('category', 'other')
        keywords = ', '.join(a.get('keywords', [])[:3])
        article_list.append(f"{i+1}. [{category}] {title}\n   摘要: {summary}\n   关键词: {keywords}")

    articles_str = "\n\n".join(article_list)

    return f"""{SYSTEM_PROMPT_INSIGHTS}

## 今日精选文章

{articles_str}

---

请基于以上文章，输出三个模块的启示。

## 输出格式（严格 JSON）

{{
  "techTrend": "技术风向：2-3 句话。指出真正值得投入的技术方向，要有具体理由，不是'AI 很重要'这种废话。",
  "deepThought": "深度思考：2-3 句话。提出一个反直觉或引人深思的问题/观点，可以有争议性。",
  "moneyShot": "变现机会：2-3 句话。从今天的内容中挖掘具体的商业化/投资机会，越具体越好，包括目标用户、痛点、为什么现在是好时机。"
}}

## 写作要求

- 每个模块 2-3 句话，总共不超过 200 字
- 必须有具体的技术名词、公司名、数据或场景
- 宁可犀利也不要平庸
- 如果某篇文章特别重要，可以点名引用
"""


def parse_insights_response(response: str) -> dict:
    """Parse insights response from LLM.

    Returns:
        Dict with techTrend, deepThought, moneyShot
    """
    import re

    response = response.strip()

    # Strip markdown code blocks if present
    if response.startswith('```'):
        response = re.sub(r'^```(?:json)?\n?', '', response)
        response = re.sub(r'\n?```$', '', response)

    try:
        data = json.loads(response)
        return {
            'tech_trend': data.get('techTrend', ''),
            'deep_thought': data.get('deepThought', ''),
            'money_shot': data.get('moneyShot', ''),
        }
    except json.JSONDecodeError:
        return {
            'tech_trend': '',
            'deep_thought': '',
            'money_shot': '',
        }


# =============================================================================
# 被淘汰文章说明
# =============================================================================

def get_rejected_prompt(selected: List[dict], rejected: List[dict]) -> str:
    """Generate prompt for explaining rejected articles.

    Args:
        selected: List of selected articles with title, score
        rejected: List of rejected articles with title, score, category
    """
    selected_str = "\n".join([
        f"- {s.get('title', '')[:50]} (评分: {s.get('score', 0)}/30)"
        for s in selected[:5]
    ])

    rejected_str = "\n".join([
        f"- [{r.get('category', 'other')}] {r.get('title', '')[:50]} (评分: {r.get('score', 0)}/30)"
        for r in rejected[:5]
    ])

    return f"""你是技术日报编辑。今日有 {len(selected)} 篇入选，{len(rejected)} 篇未入选。

## 入选文章（部分）
{selected_str}

## 未入选文章
{rejected_str}

请用 2-3 句话简要说明：
1. 这些未入选文章大致是什么内容
2. 为什么没有入选（如：评分较低、与主题关联度不够、时效性不足等）
3. 如果有价值，可以提及哪类读者可能感兴趣

风格要求：
- 直接说重点，不用"以下是..."开头
- 可以有轻微的"惋惜感"，比如"如果你对XX感兴趣，这篇值得一看"
- 不需要逐篇解释，做一个整体说明

直接返回纯文本，不要 JSON，不要 markdown 格式。"""


# =============================================================================
# 辅助函数
# =============================================================================
