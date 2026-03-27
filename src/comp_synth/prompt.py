"""Prompts for LLM-based content extraction and analysis."""

# DOM Extraction Prompts
DOM_PROMPTS = {
"LIST_ITEM_SELECTOR": """分析以下列表页 HTML 结构，生成 CSS selectors 映射，用于提取列表中的每个文章条目。

需要生成 selectors 的字段：
- item_container: 包裹整个文章条目的容器选择器（如 article, .post-item, .entry）
- url: 文章链接的选择器（通常是容器内的 <a> 标签）
- title: 文章标题的选择器（通常是 h1-h6 或带标题类的元素）
- summary: 文章摘要的选择器（通常是 p.summary, .excerpt, .description 等）
- publish_date: 文章发布的时间

请直接返回 JSON 格式：
{
    "item_container": "CSS selector for item container",
    "url": "CSS selector for article link",
    "title": "CSS selector for article title",
    "summary": "CSS selector for article summary",
    "publish_date": "CSS selector for article summary"
}

规则：
- item_container 应该选中列表中的每一个文章条目
- url 应该是容器内的链接选择器
- title , summary 和 publish_date 是容器内相应元素的选择器
- 使用简洁高效的 CSS 选择器
- 优先使用 class 和 id
""",

"LIST_ITEM_EXTRACT": """你是一个专业的网页内容提取专家。你的任务是从列表页 HTML 中提取所有文章条目信息。

需要提取的字段：
- url: 文章详情页的完整 URL
- title: 文章标题
- summary: 文章摘要（如果没有摘要则为空字符串）

请直接返回 JSON 格式，不要 markdown 代码块：
{
    "items": [
        {"url": "https://example.com/article1", "title": "标题1", "summary": "摘要1"},
        {"url": "https://example.com/article2", "title": "标题2", "summary": "摘要2"}
    ]
}

规则：
- 只提取主要文章内容，不要包含导航、广告、侧边栏等
- url 必须是完整的绝对 URL
- 如果某个字段不存在，用空字符串 ""
- items 始终是数组，即使只有一篇文章
""",
}

# Content Analyst Prompt (used in nodes.py summarize)
CONTENT_ANALYST_PROMPT = """你是一个内容分析师。你将收到一组文章。
你的任务：
1. 将它们按主题/话题分组（创建有意义的主题名称）。
2. 为每个主题写一段简洁的总结（2-3 句话概括关键要点）。
3. 为每个主题下的每篇文章写一句话总结。

以如下 JSON 格式回复：
{
  "topics": [
    {
      "topic": "主题名称",
      "summary": "主题整体总结...",
      "articles": [
        {"index": 1, "title": "...", "summary": "...", "url": "..."}
      ]
    }
  ]
}

规则：
- 每篇文章必须出现在恰好一个主题中。
- 如果文章之间没有共同主题，每篇单独一个主题。
- 使用原始文章的标题,URL,不要修改。
- 使用原始文章的summary, 可以总结精简到100字左右
- 总结要简洁且有信息量。
- 仅回复 JSON，不要 markdown 代码块。"""

# Report Generator Prompt (used in nodes.py publish)
REPORT_GENERATOR_PROMPT = """你是一个内容报告生成专家。你的任务是根据提供的主题分组信息，生成一篇结构化的 Markdown 报告。

## 报告结构要求
开头概要 -> 各主题(主题title 主题概要 各文章title+url+summary) -> 结语以及相关方向推荐

## 结构实例
```
# 内容摘要 - 2026-03-26

## 概要
今日共采集12篇文章，涵盖AI技术、市场动态、开源项目三个主要领域，整体呈现技术发展与商业应用并行的态势。

## AI技术
### 概要
AI领域今日重点关注模型优化和部署效率提升，多篇文章讨论了模型压缩和推理加速的最新进展。

**文章列表：**
1. [Llama 3.1 Inference Optimization Guide](https://example.com/llama3) - 详细介绍了如何通过量化技术将推理速度提升2倍
2. [Mistral Open Weights Release](https://example.com/mistral) - Mistral发布新型开源模型，参数规模缩小30%但性能持平



## 市场动态
### 概要
市场动态方面，投资并购持续活跃，多家AI初创公司获得新一轮融资。

**文章列表：**
1. [AI Startup Funding Roundup](https://example.com/funding) - 本月AI领域融资总额超过50亿美元
2. [Big Tech AI Acquisitions](https://example.com/acquisitions) - 各大科技公司加速布局AI并购

## 结语
资本持续涌入AI赛道，技术创新与商业落地形成良性循环。最近AI商业落地爆火, 建议关注AI自媒体内容生成,AI初创服务等方面

```

## 注意:
1. 文章列表中引用文章summary时, 不要修改和总结, 直接使用
2. 语言生动, 可以加入emoji, 但是不要加入过多emoji
"""
