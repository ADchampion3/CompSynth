# Crawler 爬取流程日志与测试增强

## 目标

为 `AdaptiveWebCrawler` 添加详细的爬取流程日志，并编写测试用例覆盖所有提取方法（用户Selector、LLM学习、DBSelector）。

## 架构

### CrawlResult 结构

```python
class CrawlResult:
    """爬取结果，包含过程信息和提取结果"""
    url: str
    extraction_method: str  # "user_selector" | "db_selector" | "llm_learning" | "heuristic"
    process_steps: list[str]  # 每一步的日志
    raw_html_size: int
    structured_before: dict  # 原始提取结果（未经处理）
    structured_after: WebPageItem  # 最终结构化数据
    success: bool
    error: str | None
```

### 日志格式规范

每个提取步骤输出：
```
[Step N] <提取方法> <操作描述>
[Data] <关键数据，如 selector、提取的字段>
[Result] <成功/失败> | title=xxx | content长度=xxx
```

### 三种提取方法

1. **用户 Selector** (`user_selector`)
   - 输入：`source_config` 中包含 `selectors`
   - 日志：显示用户传入的 selectors 和提取结果

2. **DB Selector** (`db_selector`)
   - 输入：SchemaStore 中已存储的 selectors
   - 日志：显示从 DB 加载的 selectors 和提取结果

3. **LLM 学习** (`llm_learning`)
   - 输入：无现有 selectors，首次访问触发 LLM
   - 日志：显示 LLM 生成的 selectors 和提取结果

4. **启发式后备** (`heuristic`)
   - 输入：上述方法全部失败
   - 日志：显示使用的启发式规则

## 实现步骤

1. **修改 `AdaptiveWebCrawler`**
   - 新增 `CrawlResult` dataclass
   - 在 `_crawl_detail_page` 和 `_crawl_list_page` 添加详细日志
   - 每个提取步骤记录：`extraction_method`, `process_steps`, `raw_html_size`, `structured_data`

2. **修改 `DOMExtractor`**
   - 为 `extract_with_selectors`, `extract`, `generate_selectors` 添加日志
   - 输出原始 HTML 大小、提取的字段、是否成功

3. **新增测试类 `TestCrawlerExtractionMethods`**
   - `test_user_defined_selector`: 测试用户传入 selectors
   - `test_llm_learning_selector`: 测试 LLM 学习生成 selectors（mock LLM）
   - `test_db_selector_reuse`: 测试从 DB 加载并复用 selectors
   - `test_all_methods_on_same_url`: 对同一 URL 测试所有方法并比较结果

4. **日志输出验证**
   - 每个测试运行后输出汇总：
     ```
     === 爬取流程汇总 ===
     URL: https://example.com
     使用方法: db_selector
     提取耗时: 1.23s
     原始HTML: 45678 bytes
     提取结果: title=xxx, content长度=1234
     ```

## 关键设计决策

- **日志级别**：使用 `logger.info` 输出详细信息
- **不修改返回类型**：`fetch()` 仍返回 `list[WebPageItem]`，`CrawlResult` 仅用于日志记录
- **测试隔离**：每个测试使用临时 DB，避免状态污染
- **Mock LLM**：LLM 相关测试使用 mock，避免真实 API 调用

## 测试场景

| 测试 | 输入 HTML | Selectors | 预期方法 |
|------|-----------|-----------|----------|
| 用户Selector | 标准 article | 用户传入 | user_selector |
| DB Selector | 标准 article | DB 已有 | db_selector |
| LLM Learning | 复杂结构 | 无 | llm_learning |
| Heuristic | 非标准 | 无 | heuristic |
