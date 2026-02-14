"""
Prompt templates for AI Daily News Bot.
All prompts are designed for Chinese language output.
"""

from typing import List, Optional


# =============================================================================
# System Prompts
# =============================================================================

SYSTEM_PROMPT_FILTER = """你是一个专业的新闻筛选助手，负责判断新闻内容是否值得报道。

你的领域关注范围：
1. AI 技术：机器学习、LLM、深度学习、AI 产品发布、技术突破
2. AI 投资：AI 领域融资、VC 动态、初创公司、IPO
3. Web3：加密货币、区块链、DeFi、NFT、监管政策

判断标准：
- 具有新闻价值（新产品、重大更新、融资、政策变化、技术突破）
- 不是纯教程、使用体验分享、营销软文
- 信息来源可靠，内容具体

请严格按照要求回答 YES 或 NO。"""


SYSTEM_PROMPT_SUMMARY = """你是一个专业的新闻摘要编辑，擅长用简洁的语言总结新闻要点。

要求：
- 摘要不超过 100 字
- 突出最重要的信息
- 语言简洁专业
- 保持客观中立"""


SYSTEM_PROMPT_KEYWORDS = """你是一个关键词提取专家，负责从新闻中提取关键信息。

要求：
- 提取 3-5 个关键词
- 关键词应该反映新闻的核心主题
- 包含公司名、技术名、产品名等重要实体
- 返回 JSON 数组格式"""


SYSTEM_PROMPT_SCORE = """你是一个新闻价值评估专家，负责对新闻进行打分。

打分标准（0-100分）：
- 重要性（40%）：是否影响行业格局、是否是重大突破
- 时效性（30%）：是否是最新的消息、是否独家
- 相关性（30%）：与 AI/投资/Web3 的关联程度

请只返回一个 0-100 的整数分数。"""


SYSTEM_PROMPT_REPORT = """你是一个科技新闻编辑，负责生成每日早报。

要求：
1. 按分类组织内容（AI技术、AI投资、Web3）
2. 每条新闻包含：标题、简洁摘要、来源链接
3. 使用 Markdown 格式
4. 添加目录和适当的标题层级
5. 语言简洁专业，适合技术人员阅读
6. 每个分类下按重要性排序"""


# =============================================================================
# Prompt Functions
# =============================================================================

def get_filter_prompt(title: str, content: str) -> str:
    """Generate prompt for filtering news relevance."""
    return f"""请判断以下新闻是否值得报道：

标题: {title}

内容: {content[:1000] if content else '（无内容）'}

请只回答 YES 或 NO。"""


def get_summary_prompt(title: str, content: str) -> str:
    """Generate prompt for summarizing news."""
    return f"""请为以下新闻生成一句话摘要（不超过100字）：

标题: {title}

内容: {content[:2000] if content else '（无内容）'}

摘要："""


def get_keywords_prompt(title: str, content: str) -> str:
    """Generate prompt for extracting keywords."""
    return f"""请从以下新闻中提取 3-5 个关键词：

标题: {title}

内容: {content[:1000] if content else '（无内容）'}

请以 JSON 数组格式返回关键词，例如：["OpenAI", "GPT-5", "发布"]

关键词："""


def get_score_prompt(title: str, content: str) -> str:
    """Generate prompt for scoring news importance."""
    return f"""请为以下新闻打分（0-100分）：

标题: {title}

内容: {content[:1000] if content else '（无内容）'}

考虑因素：
- 重要性：是否影响行业
- 时效性：是否最新消息
- 相关性：与 AI/投资/Web3 的关联程度

请只返回一个 0-100 的整数分数："""


def get_report_prompt(items: List[dict], date_str: str) -> str:
    """Generate prompt for creating daily report.

    Args:
        items: List of processed news items with title, summary, category, url
        date_str: Date string for the report

    Returns:
        Formatted prompt string
    """
    # Group items by category
    ai_items = []
    investment_items = []
    web3_items = []

    for item in items:
        category = item.get("category", "mixed")
        if category == "ai":
            ai_items.append(item)
        elif category == "investment":
            investment_items.append(item)
        elif category == "web3":
            web3_items.append(item)
        else:
            # Mixed items go to AI by default
            ai_items.append(item)

    # Format items by category
    def format_items(item_list: List[dict]) -> str:
        if not item_list:
            return "（无）"

        formatted = []
        for i, item in enumerate(item_list, 1):
            title = item.get("title", "无标题")
            summary = item.get("summary", "无摘要")
            url = item.get("url", "")

            formatted.append(f"""
{i}. {title}
   摘要：{summary}
   来源：{url}
""")
        return "\n".join(formatted)

    prompt = f"""请根据以下信息生成 {date_str} 的每日早报。

---

## AI 技术新闻:
{format_items(ai_items)}

---

## AI 投资新闻:
{format_items(investment_items)}

---

## Web3 新闻:
{format_items(web3_items)}

---

请生成 Markdown 格式的早报，包含：
1. 主标题和日期
2. 目录
3. 三个分类的新闻内容
4. 每条新闻包含标题、摘要和来源链接

早报内容："""

    return prompt


def get_dedup_prompt(new_title: str, old_titles: List[str]) -> str:
    """Generate prompt for checking duplicate news.

    Args:
        new_title: Title of the new news item
        old_titles: List of existing news titles to compare against

    Returns:
        Formatted prompt string
    """
    old_titles_str = "\n".join([f"- {t}" for t in old_titles])

    return f"""请判断以下新闻是否与已有新闻重复：

新新闻标题: {new_title}

已有新闻标题:
{old_titles_str}

如果新新闻与已有新闻报道的是同一事件，请回答 DUPLICATE。
如果是不同事件或不同角度的报道，请回答 UNIQUE。

请只回答 DUPLICATE 或 UNIQUE："""


# =============================================================================
# Utility Functions
# =============================================================================

def parse_keywords_response(response: str) -> List[str]:
    """Parse keywords from LLM response.

    Args:
        response: Raw LLM response string

    Returns:
        List of keywords
    """
    import json
    import re

    # Try to find JSON array in response
    json_match = re.search(r'\[.*?\]', response, re.DOTALL)
    if json_match:
        try:
            keywords = json.loads(json_match.group())
            if isinstance(keywords, list):
                return [str(k).strip() for k in keywords if k]
        except json.JSONDecodeError:
            pass

    # Fallback: split by comma or newline
    cleaned = response.strip().strip('[]').strip('"\'')
    if ',' in cleaned:
        return [k.strip().strip('"\'') for k in cleaned.split(',') if k.strip()]
    elif '\n' in cleaned:
        return [k.strip().strip('"\'') for k in cleaned.split('\n') if k.strip()]
    else:
        return [cleaned] if cleaned else []


def parse_score_response(response: str) -> int:
    """Parse score from LLM response.

    Args:
        response: Raw LLM response string

    Returns:
        Integer score between 0-100
    """
    import re

    # Find first number in response
    match = re.search(r'\d+', response)
    if match:
        score = int(match.group())
        return min(max(score, 0), 100)  # Clamp to 0-100

    return 50  # Default score


def parse_filter_response(response: str) -> bool:
    """Parse filter response.

    Args:
        response: Raw LLM response string

    Returns:
        True if news should be kept, False if should be discarded
    """
    return response.strip().upper().startswith('YES')
