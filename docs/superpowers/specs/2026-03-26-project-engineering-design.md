# CompSynth 工程化重构设计

## 目标

1. **删除无用代码** — 全面扫描并移除 unused imports、variables、孤立模块
2. **标准化目录结构** — 采用 `src/` 布局
3. **依赖分层隔离** — core / integrations / app 三层分离

## 目录结构

```
src/comp_synth/
├── core/                    # 核心层：无外部依赖
│   ├── __init__.py
│   ├── models/              # Pydantic models（base、rss、web、article等）
│   ├── interfaces/          # 抽象基类（Publisher、Store、Crawler等）
│   └── types.py             # 共用类型定义、常量
│
├── integrations/            # 集成层：依赖外部库
│   ├── __init__.py
│   ├── crawlers/            # 多种爬虫实现
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── web.py
│   │   ├── rss.py
│   │   ├── adaptive.py
│   │   └── extractors/      # DOM提取器
│   │       ├── __init__.py
│   │       └── dom.py
│   ├── stores/              # 存储实现
│   │   ├── __init__.py
│   │   ├── vector.py        # ChromaDB
│   │   └── sqlite.py        # SQLite
│   └── llm/                 # LLM集成
│       ├── __init__.py
│       └── registry.py
│
├── app/                     # 应用层：胶水代码
│   ├── __init__.py
│   ├── agent/               # Agent逻辑
│   ├── orchestration/       # LangGraph编排
│   │   ├── __init__.py
│   │   ├── graph.py
│   │   ├── nodes.py
│   │   └── state.py
│   ├── publishers/          # 发布器
│   │   ├── __init__.py
│   │   └── base.py
│   ├── main.py              # 入口点
│   └── config.py            # 配置
│
└── shared/                  # 跨层共享（logger等）
    ├── __init__.py
    └── logging.py
```

## 三层依赖规则

```
core (无外部依赖)
  ├── models      ← 被所有层使用
  ├── interfaces  ← 被 integrations 实现
  └── types       ← 被所有层使用

integrations
  ├── crawlers    ← 被 app.orchestration 调用
  ├── stores      ← 被 app.orchestration 调用
  └── llm         ← 被 app.agent 调用

app
  ├── orchestration ← 被 main 组装
  ├── agent         ← 被 orchestration 调用
  ├── publishers    ← 被 orchestration 调用
  └── config        ← 被所有层使用
```

**依赖方向：core → integrations → app，禁止反向依赖**

## Unused Code 处理

### 检测工具
- `ruff check --select=F401,F841` — 检测 unused imports 和 variables
- `ruff check --select=F401` — 配合 `--add-noqa` 分析孤立模块
- 手动审查工具报告，确认后删除

### 处理范围
- 未使用的 import
- 未使用的变量
- 孤立的不被任何模块引用的文件
- 已被注释掉的废弃代码

## 迁移步骤

1. **创建新目录结构**
   - 创建 `src/comp_synth/{core,integrations,app,shared}/`
   - 创建各子目录的 `__init__.py`

2. **移动代码文件**
   - `schemas/` → `core/models/`
   - `crawler/` → `integrations/crawlers/`
   - `store/` → `integrations/stores/`
   - `llm/` → `integrations/llm/`
   - `agent/` → `app/agent/`
   - `orchestrator/` → `app/orchestration/`
   - `publisher/` → `app/publishers/`
   - `utils/logger_config.py` → `shared/logging.py`
   - `config.py` → `app/config.py`
   - `main.py` → `app/main.py`

3. **修复 import 路径**
   - 更新所有 `from ... import ...` 语句
   - 确保依赖方向正确

4. **删除无用代码**
   - 运行 ruff 检测
   - 审查并删除确认无用的代码

5. **验证**
   - 运行 `pytest` 确保逻辑不变
   - 运行 `ruff check` 确保代码质量

6. **清理**
   - 删除 `lib_demo/`
   - 删除旧 `src/comp_synth/` 结构

7. **更新 pyproject.toml**
   - 确保 `src` 布局配置正确

## 约束

- **不修改代码逻辑** — 只改文件位置和 import 路径
- **保持功能不变** — 所有测试必须通过
- **依赖方向严格** — 禁止 core → app 或 integrations → core 的反向依赖
