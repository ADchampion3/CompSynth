# 用户订阅源 CSS Selector 配置实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在订阅配置中支持用户自定义 CSS Selector，实现优先级提取流程

**Architecture:** 扩展 subscriptions.yaml 配置格式，修改 AdaptiveWebCrawler 支持用户定义 selectors 的优先使用，实现四层提取：用户配置 > DB > LLM > 启发式

**Tech Stack:** Python, YAML, CSS Selectors, BeautifulSoup, LLM

---

## 文件结构

- `subscriptions.example.yaml` - 添加 selectors 字段示例
- `src/comp_synth/orchestrator/nodes.py` - 传递 user_selectors 到 crawler
- `src/comp_synth/crawler/adaptive_crawler.py` - 实现优先级提取逻辑（列表页 + 详情页）
- `src/comp_synth/crawler/dom_extractor.py` - 确保空数据可检测
- `tests/test_crawler.py` - 新增测试用例

---

## 实现任务

### Task 1: 更新 subscriptions.example.yaml 添加 selectors 示例

**Files:**
- Modify: `subscriptions.example.yaml`

- [ ] **Step 1: 添加 selectors 字段示例**

```yaml
sources:
  - type: rss
    url: https://example.com/feed.xml
    name: Example Blog
  - type: web
    url: https://tech.example.com/
    name: Example Tech
    selectors:  # 可选：用户自定义 CSS selectors
      item_container: ".post-container"
      url: ".post-title a"
      title: ".post-title"
      summary: ".post-excerpt"
```

- [ ] **Step 2: Commit**

```bash
git add subscriptions.example.yaml
git commit -m "docs: add CSS selectors example to subscriptions config"
```

---

### Task 2: 修改 nodes.py 传递 user_selectors

**Files:**
- Modify: `src/comp_synth/orchestrator/nodes.py:34-50`

- [ ] **Step 1: 查看当前 fetch_sources 完整代码**

```bash
grep -n "crawler.fetch" src/comp_synth/orchestrator/nodes.py
```

- [ ] **Step 2: 修改 crawler.fetch() 调用，传递 user_selectors**

将:
```python
items = await crawler.fetch(source)
```

改为:
```python
user_selectors = source.get("selectors", {})
items = await crawler.fetch(source, user_selectors=user_selectors)
```

- [ ] **Step 3: Commit**

```bash
git add src/comp_synth/orchestrator/nodes.py
git commit -m "feat(nodes): pass user_selectors to crawler"
```

---

### Task 3: 修改 AdaptiveWebCrawler 核心方法签名

**Files:**
- Modify: `src/comp_synth/crawler/adaptive_crawler.py`

- [ ] **Step 1: 修改 fetch() 方法签名**

```python
async def fetch(self, source_config: dict, user_selectors: dict = None) -> list[WebPageItem]:
```

- [ ] **Step 2: 修改 _crawl_list_page() 方法签名**

```python
async def _crawl_list_page(self, html: str, url: str, user_selectors: dict = None) -> list[WebPageItem]:
```

- [ ] **Step 3: 修改 _crawl_detail_page() 方法签名**

```python
async def _crawl_detail_page(self, html: str, url: str, user_selectors: dict = None) -> list[WebPageItem]:
```

- [ ] **Step 4: 修改 fetch() 内部分支调用**

```python
if self._is_list_page(html):
    return await self._crawl_list_page(html, url, user_selectors)
else:
    return await self._crawl_detail_page(html, url, user_selectors)
```

- [ ] **Step 5: Commit**

```bash
git add src/comp_synth/crawler/adaptive_crawler.py
git commit -m "feat(adaptive_crawler): add user_selectors param to fetch methods"
```

---

### Task 4: 修改 _extract_list_items 实现优先级提取

**Files:**
- Modify: `src/comp_synth/crawler/adaptive_crawler.py:175-207`

- [ ] **Step 1: 修改方法签名**

```python
async def _extract_list_items(
    self,
    html: str,
    base_url: str,
    site_name: str,
    user_selectors: dict = None
) -> list[dict]:
```

- [ ] **Step 2: 添加优先级提取逻辑（含 URL join）**

```python
# 步骤1：尝试用户配置的 selectors
if user_selectors:
    items = self._dom_extractor.extract_list_items_with_selectors(html, user_selectors)
    if items and self._has_valid_data(items):
        logger.info(f"使用用户配置的 selectors 提取列表项")
        # 转换为绝对 URL
        for item in items:
            if item.get("url"):
                item["url"] = urljoin(base_url, item["url"])
        return self._deduplicate_items(items)

# 步骤2：DB selectors
schema = self._schema_store.get(site_name)
if schema and schema.list_selectors:
    items = self._dom_extractor.extract_list_items_with_selectors(html, schema.list_selectors)
    if items and self._has_valid_data(items):
        logger.info(f"使用 DB 的 list_selectors 提取列表项")
        for item in items:
            if item.get("url"):
                item["url"] = urljoin(base_url, item["url"])
        return self._deduplicate_items(items)

# 步骤3：LLM 学习
if self._schema_store.can_use_llm(site_name):
    llm_items = await self._learn_list_item_schema(html, site_name)
    if llm_items:
        for item in llm_items:
            if item.get("url"):
                item["url"] = urljoin(base_url, item["url"])
        return self._deduplicate_items(llm_items)

# 步骤4：启发式后备
logger.info(f"使用启发式方法提取列表项")
return await self._extract_list_items_heuristic(html, base_url)
```

- [ ] **Step 3: 添加新的 _has_valid_data 辅助方法**

在 `AdaptiveWebCrawler` 类中添加新方法：

```python
def _has_valid_data(self, items: list[dict]) -> bool:
    """检查是否有有效数据（至少 title 和 url 非空）"""
    return any(item.get("title") and item.get("url") for item in items)
```

- [ ] **Step 4: Commit**

```bash
git add src/comp_synth/crawler/adaptive_crawler.py
git commit -m "feat(adaptive_crawler): implement priority-based list items extraction"
```

---

### Task 5: 修改 _crawl_detail_page 支持 user_selectors

**Files:**
- Modify: `src/comp_synth/crawler/adaptive_crawler.py:364-447`

- [ ] **Step 1: 在详情页提取逻辑中添加 user_selectors 优先级**

在 `_crawl_detail_page` 方法开头获取 site_name 后：

```python
# 步骤0：尝试用户配置的 selectors
if user_selectors and user_selectors.get("content"):
    schema_result = await self._extract_with_schema(html, user_selectors)
    if schema_result.get("content"):
        item = self._build_item(
            url=url,
            title=schema_result.get("title", "") or readability_result.get("title", ""),
            content=schema_result.get("content", ""),
            author=schema_result.get("author", ""),
            tags=schema_result.get("tags", []),
            site_name=site_name,
        )
        self._tracker.mark_crawled("web", url)
        return [item]
```

- [ ] **Step 2: Commit**

```bash
git add src/comp_synth/crawler/adaptive_crawler.py
git commit -m "feat(adaptive_crawler): add user selectors support in detail page"
```

---

### Task 6: DOMExtractor 返回值确认

**Files:**
- Read: `src/comp_synth/crawler/dom_extractor.py:344-400`

- [ ] **Step 1: 确认 extract_list_items_with_selectors 返回类型**

查看 `extract_list_items_with_selectors` 方法，确认：
- 返回类型是 `list[dict]`
- 空结果时返回 `[]` 而非 `None`

当前实现已返回 `list[dict]`，无需修改。

- [ ] **Step 2: 如发现问题则修改**

如果返回类型不符合预期，修改为：
```python
def extract_list_items_with_selectors(...) -> list[dict]:
    # ... 现有逻辑 ...
    if not items:
        return []
    return items
```

- [ ] **Step 3: 无需 Commit（如有修改才提交）**

---

### Task 7: 添加单元测试

**Files:**
- Modify: `tests/test_crawler.py`

- [ ] **Step 1: 添加 _has_valid_data 测试**

```python
def test_has_valid_data():
    """测试 _has_valid_data 辅助方法"""
    crawler = AdaptiveWebCrawler()

    # 有效数据
    valid_items = [
        {"url": "https://example.com/1", "title": "Title 1"},
        {"url": "https://example.com/2", "title": ""},
    ]
    assert crawler._has_valid_data(valid_items) is True

    # 无有效数据
    invalid_items = [
        {"url": "https://example.com/1", "title": ""},
        {"url": "https://example.com/2", "title": ""},
    ]
    assert crawler._has_valid_data(invalid_items) is False

    # 空列表
    assert crawler._has_valid_data([]) is False
```

- [ ] **Step 2: 运行测试验证**

```bash
pytest tests/test_crawler.py::test_has_valid_data -v
```

Expected: PASS

- [ ] **Step 3: 添加 extract_list_items_with_selectors 返回空列表测试**

```python
def test_extract_list_items_returns_empty_list():
    """测试 extract_list_items_with_selectors 返回空列表"""
    extractor = DOMExtractor()
    html = "<html><body><div class='no-match'></div></body></html>"
    selectors = {
        "item_container": ".post",
        "url": "a",
        "title": "h2",
        "summary": "p"
    }
    result = extractor.extract_list_items_with_selectors(html, selectors)
    assert result == []
```

- [ ] **Step 4: 运行测试验证**

```bash
pytest tests/test_crawler.py::test_extract_list_items_returns_empty_list -v
```

Expected: PASS

- [ ] **Step 5: 添加 _has_valid_data 单元测试**

```python
def test_has_valid_data():
    """测试 _has_valid_data 辅助方法正确识别有效/无效数据"""
    crawler = AdaptiveWebCrawler()

    # 有效数据：title 和 url 都非空
    valid_items = [
        {"url": "https://example.com/1", "title": "Title 1"},
        {"url": "https://example.com/2", "title": ""},
    ]
    assert crawler._has_valid_data(valid_items) is True

    # 无效数据：只有 url，title 为空
    url_only_items = [
        {"url": "https://example.com/1", "title": ""},
    ]
    # 注意：url 非空但 title 为空，按当前逻辑返回 False
    assert crawler._has_valid_data(url_only_items) is False

    # 无效数据：title 非空但 url 为空
    title_only_items = [
        {"url": "", "title": "Title Only"},
    ]
    assert crawler._has_valid_data(title_only_items) is False

    # 无效数据：全部为空
    invalid_items = [
        {"url": "", "title": ""},
    ]
    assert crawler._has_valid_data(invalid_items) is False

    # 空列表
    assert crawler._has_valid_data([]) is False
```

- [ ] **Step 6: Commit**

```bash
git add tests/test_crawler.py
git commit -m "test(adaptive_crawler): add user_selectors unit tests"
```

---

### Task 8: 集成测试 - 完整流程验证

- [ ] **Step 1: 运行完整流程**

```bash
python -c "
import asyncio
import shutil
import os
from comp_synth.orchestrator.graph import build_pipeline

# 清理数据库
for f in ['data/crawl_state.db', 'data/chroma']:
    if os.path.exists(f):
        if os.path.isdir(f):
            shutil.rmtree(f)
        else:
            os.remove(f)

async def run():
    pipeline = build_pipeline()
    result = await pipeline.ainvoke({
        'sources': [],
        'raw_items': [],
        'new_items': [],
        'topic_groups': [],
        'report': '',
        'publish_results': {},
        'errors': [],
    })
    return result

result = asyncio.run(run())
status = result.get('publish_results', {}).get('status', 'unknown')
print(f'Status: {status}')
" 2>&1 | grep -E '(使用|Status|Error)'
```

- [ ] **Step 2: 验证降级流程**

运行后检查日志中是否出现 "使用用户配置的 selectors" 或降级到 "使用 DB 的 list_selectors"

- [ ] **Step 3: Commit**

---

## 验证

1. **单元测试**: `pytest tests/test_crawler.py -v -k "not real_llm"`
2. **集成测试**: 运行完整流程，检查日志
3. **降级测试**: 配置无效 selectors，验证降级行为

---

## 涉及文件汇总

| 文件 | 改动类型 |
|------|----------|
| `subscriptions.example.yaml` | 修改 |
| `src/comp_synth/orchestrator/nodes.py` | 修改 |
| `src/comp_synth/crawler/adaptive_crawler.py` | 修改 |
| `src/comp_synth/crawler/dom_extractor.py` | 修改（确认返回类型）|
| `tests/test_crawler.py` | 修改 |
