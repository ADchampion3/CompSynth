# 用户订阅源 CSS Selector 配置设计

## 背景

当前系统通过 `AdaptiveWebCrawler` 支持多层提取：
1. DB 中已存储的 CSS selectors
2. LLM 学习并保存 selectors
3. 启发式提取

用户希望在 `subscriptions.yaml` 中直接定义 CSS selectors，实现：
- **用户控制**：用户自己决定如何提取
- **优先级明确**：用户定义 > DB > LLM > 启发式
- **降级策略**：用户 selector 匹配但无数据时，继续尝试低优先级方案

## 配置格式

### subscriptions.yaml 扩展

```yaml
sources:
  - type: web
    url: https://tech.meituan.com/
    name: 美团技术
    selectors:  # 可选，用户自定义
      item_container: ".post-container"
      url: ".post-title a"
      title: ".post-title"
      summary: ".post-excerpt"
```

### 字段说明

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `selectors` | dict | 否 | CSS selectors 配置 |
| `selectors.item_container` | str | 是* | 文章容器选择器（*列表页必填） |
| `selectors.url` | str | 是* | 文章链接选择器（*列表页必填） |
| `selectors.title` | str | 否 | 标题选择器 |
| `selectors.summary` | str | 否 | 摘要选择器 |

## 提取流程

```
用户定义的 selectors（subscriptions.yaml）
    ↓ 存在但匹配无数据 或 不存在
DB 中的 selectors（SchemaStore）
    ↓ 存在但匹配无数据 或 不存在
LLM 提取 + 学习（每站每天 1 次）
    ↓ 失败
启发式提取（后备）
```

### 关键规则

1. **用户定义优先**：用户定义的 selectors 拥有最高优先级
2. **降级条件**：
   - 用户 selector 存在但提取结果为空 → 降级到 DB
   - 用户 selector 不存在 → 直接降级到 DB
3. **低优先级不能覆盖高优先级**：即使低优先级方案有数据，也返回空

## 实现

### 1. 修改 `nodes.py`

```python
async def fetch_sources(state: PipelineState) -> dict:
    """从所有订阅源采集内容"""
    # ... 现有代码 ...
    for source in sources:
        # 从配置中获取用户定义的 selectors
        user_selectors = source.get("selectors", {})
        # 传递给 crawler
        items = await crawler.fetch(source, user_selectors=user_selectors)
```

### 2. 修改 `AdaptiveWebCrawler.fetch()`

```python
async def fetch(self, source_config: dict, user_selectors: dict = None) -> list[WebPageItem]:
    """
    user_selectors: 用户在 subscriptions.yaml 中定义的 selectors
    """
    # 检测页面类型
    if self._is_list_page(html):
        return await self._crawl_list_page(html, url, user_selectors)
    else:
        return await self._crawl_detail_page(html, url, user_selectors)
```

### 3. 修改 `_extract_list_items()`

```python
async def _extract_list_items(
    self,
    html: str,
    base_url: str,
    site_name: str,
    user_selectors: dict = None
) -> list[dict]:
    """
    优先级提取：
    1. user_selectors（用户配置）
    2. DB selectors（SchemaStore）
    3. LLM 学习
    4. 启发式后备
    """
    # 步骤1：尝试用户配置的 selectors
    if user_selectors:
        items = self._dom_extractor.extract_list_items_with_selectors(html, user_selectors)
        if items and self._has_valid_data(items):
            return self._normalize_and_deduplicate(items, base_url)

    # 步骤2：DB selectors
    schema = self._schema_store.get(site_name)
    if schema and schema.list_selectors:
        items = self._dom_extractor.extract_list_items_with_selectors(html, schema.list_selectors)
        if items and self._has_valid_data(items):
            return self._normalize_and_deduplicate(items, base_url)

    # 步骤3：LLM 学习
    if self._schema_store.can_use_llm(site_name):
        items = await self._learn_list_item_schema(html, site_name)
        if items:
            return self._normalize_and_deduplicate(items, base_url)

    # 步骤4：启发式后备
    return await self._extract_list_items_heuristic(html, base_url)

def _has_valid_data(self, items: list[dict]) -> bool:
    """检查是否有有效数据（至少 title 和 url 非空）"""
    return any(item.get("title") and item.get("url") for item in items)
```

### 4. 修改 `DOMExtractor.extract_list_items_with_selectors()`

确保返回结果能区分"提取到空"和"未提取到"。

## 文件修改

| 文件 | 改动 |
|------|------|
| `subscriptions.example.yaml` | 添加 selectors 字段示例 |
| `src/comp_synth/orchestrator/nodes.py` | 传递 user_selectors 到 crawler |
| `src/comp_synth/crawler/adaptive_crawler.py` | 优先使用用户 selectors |
| `src/comp_synth/crawler/dom_extractor.py` | 确保空数据可检测 |

## 测试

1. **单元测试**：用户 selectors 有效提取
2. **单元测试**：用户 selectors 为空时降级到 DB
3. **单元测试**：用户 selectors 无数据时降级到 DB
4. **集成测试**：完整流程验证

## 示例

```yaml
# subscriptions.yaml
sources:
  - type: web
    url: https://tech.meituan.com/
    name: 美团技术
    selectors:
      item_container: ".post-container"
      url: ".post-title a"
      title: ".post-title"
      summary: ".post-excerpt"
  - type: web
    url: https://blog.example.com/
    name: Example Blog
    # 无 selectors，降级到 DB/LLM/启发式
```
