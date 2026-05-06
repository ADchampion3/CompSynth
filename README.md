# CompSynth

**一天内容，一网打尽。**

本地内容聚合与发布系统。抓取 RSS、Web（静态/JS渲染）内容，通过 LLM 生成摘要，输出 Markdown 日报。

[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/) [![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=flat&logo=fastapi)](https://fastapi.tiangolo.com/) [![React](https://img.shields.io/badge/React-18-61DAFB?style=flat&logo=react)](https://react.dev/) [![TypeScript](https://img.shields.io/badge/TypeScript-5-blue?style=flat&logo=typescript)](https://www.typescriptlang.org/) [![ChromaDB](https://img.shields.io/badge/ChromaDB-1.8-green?style=flat)](https://www.trychroma.com/)
[![GitHub stars](https://img.shields.io/github/stars/ADchampion3/CompSynth?style=flat)](https://github.com/ADchampion3/CompSynth/stargazers)

[Website](https://github.com/ADchampion3/CompSynth)  · [Contributing](CONTRIBUTING.md)

---

## 为什么是 CompSynth？

**CompSynth** = **Comp**osition + **Synth**esis

名字源于它的核心能力：将多个来源的内容组合（compose）成一份综合摘要（synthesize）。对于追踪技术博客和资讯的研究人员、工程师而言，这是一款本地优先的工具——数据留在本地，配置通过 YAML 管理，不需要注册账号。

<p align="center">
  <img src="docs/assets/hello-hero.png" alt="CompSynth 文章列表视图"  width="800">
</p>
<p align="center">
  <img src="docs/assets/Report-screenshot.png" alt="CompSynth 报告视图"  width="800">
</p>

<video src="docs/assets/display.mp4" width="800" controls></video>

## 功能

- **多源抓取** — RSS、Web（静态）、JavaScript 渲染页面
- **智能去重** — SQLite + ChromaDB 实现持久化去重
- **LLM 摘要** — 支持 OpenAI 和 Anthropic兼容 API
- **Web UI** — 收件箱、订阅源管理、文章阅读
- **选择器编辑器** — CSS 选择器 + LLM 辅助重提取
- **后端配置同步** — 设置页面直接修改，无需重启

---

## 快速安装

```bash
git clone https://github.com/ADchampion3/CompSynth.git
cd CompSynth
uv sync
```

---

## 快速开始

### 1. 启动

```bash
# 启动后端 API 服务器
uv run compsynth serve

# 新终端：启动前端
cd frontend
npm install   # 首次运行需要
npm run dev
```

打开 http://localhost:5173 查看 Web UI。

### 2. 配置订阅源

打开设置页面 → 订阅源管理，添加你的订阅源（支持 RSS 和 Web 两种类型）。

---

## CLI

| 命令 | 说明 |
|------|------|
| `uv run compsynth` | 运行完整流程（抓取 → 去重 → 摘要 → 发布） |
| `uv run compsynth serve` | 启动 API 服务器（默认 http://127.0.0.1:8000） |
| `uv run compsynth crawl` | 仅运行爬取 pipeline |
| `uv run compsynth dashboard` | 打印仪表盘摘要 JSON |
| `uv run compsynth reports list` | 列出已生成的报告 |
| `uv run compsynth reports get <id>` | 读取指定报告内容 |
| `uv run compsynth sources import` | 从 YAML 导入订阅源到数据库 |
| `uv run compsynth sources export` | 从数据库导出订阅源到 YAML |

---

## 架构

```
┌──────────────┐     ┌──────────────┐     ┌──────────────────┐
│   RSS        │────>│  Crawlers    │────>│   SQLite         │
│   Web        │     │  (fetch)     │     │   (dedup/tracking)
│   JavaScript │     └──────┬───────┘     └────────┬─────────┘
└──────────────┘            │                       │
                           ▼                       ▼
                    ┌──────────────┐     ┌──────────────────┐
                    │  ChromaDB    │     │   LLM            │
                    │  (vector)    │     │   (summarize)    │
                    └──────────────┘     └────────┬─────────┘
                                                  │
                    ┌──────────────┐              │
                    │  FastAPI     │<─────────────┘
                    │  (Web UI)    │
                    └──────────────┘
```

| 层级 | 技术栈 |
|------|--------|
| 后端 | Python 3.11+, FastAPI, SQLite, ChromaDB |
| 前端 | React, TypeScript, Vite |
| LLM | OpenAI 兼容 API / Anthropic |

---

## 配置

### 配置文件

| 文件 | 说明 | 优先级 |
|------|------|--------|
| `.env` | 环境变量配置（LLM API Key、存储路径等） | 高 |
| `subscriptions.yaml` | 订阅源配置（RSS/Web 列表） | 高 |
| `data/crawl_state.db` | SQLite 数据库（运行时缓存） | 低 |

### 订阅源配置 (subscriptions.yaml)

```bash
cp subscriptions.example.yaml subscriptions.yaml
```

```yaml
sources:
  - type: rss
    url: https://example.com/feed.xml
    name: 示例博客

  - type: web
    url: https://tech.example.com/
    name: 示例科技站
    selectors:
      - item_container: ".post-container"
        url: ".post-title a"
        title: ".post-title"
        summary: ".post-excerpt"
```

**type 类型**: `rss`（RSS 订阅）、`web`（静态网页）、`javascript`（JS 渲染页面）

### 配置与数据库的关系

```
subscriptions.yaml ──→ [启动时自动同步] ──→ crawl_state.db
                                                    ↓
                              ┌───────────────────────┴───────────────────────┐
                              ↓                                               ↓
                         前端读取                                         CLI/后端读取
                      (订阅源管理页面)                                   (crawl pipeline)
```

**同步规则**:
- **启动时**: `subscriptions.yaml` → 数据库（YAML 是真相来源）
- **前端修改订阅源时**: 数据库更新，并可选同步回 YAML
- **前端修改设置时**: 数据库更新，运行时生效（部分配置需重启）

### 环境变量 (.env)

LLM 等配置可直接在 Web UI 的设置页面中修改（无需编辑文件），也可通过环境变量配置：

```bash
cp .env.example .env
```

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `COMPSYNTH_OPENAI_API_KEY` | OpenAI API Key | - |
| `COMPSYNTH_ANTHROPIC_API_KEY` | Anthropic API Key | - |
| `COMPSYNTH_MODEL` | 模型名称 | gpt-4o-mini |
| `COMPSYNTH_DATA_DIR` | 数据目录 | ./data |
| `COMPSYNTH_SUBSCRIPTIONS_PATH` | 订阅源配置文件路径 | ./subscriptions.yaml |
| `COMPSYNTH_TIME_THRESHOLD_DAYS` | 内容时间阈值（天） | 7 |

完整配置参考见 `.env.example`。

---

## Roadmap

- [ ] **底层使用 RAG 做向量搜索** — 借助 RAG（检索增强生成）提升相关文章推荐的准确性
- [ ] **预处理提高 Selectors 有效性** — 爬取前预处理 URL/页面结构，减少无效 Selector
- [ ] **定时任务** — 支持配置 Cron 表达式，自动定期抓取和生成日报
- [ ] **推送功能** — 日报生成后自动推送到微信、邮件、Telegram 等平台
- [ ] **增强信息源与反爬通用性** — 支持更多网站类型，自动处理常见反爬机制（UA、代理池、验证码等）
- [ ] **封装为SKILL** — 增强CLI通用性, 封装为SKILL供Agent使用

---

## 开发

### 前置要求

- Python 3.11+
- [uv](https://github.com/astral-sh/uv)
- Node.js 18+ (前端开发)

### 安装

```bash
uv sync
cd frontend && npm install
```

### 开发

```bash
# 后端
uv run compsynth serve

# 前端
cd frontend && npm run dev
```

### 测试

```bash
uv run python -m pytest -q
uv run python -m compileall -q src tests
```
