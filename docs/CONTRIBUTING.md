# Contributing to CompSynth

## 开发环境

### 前置要求

- Python 3.11+
- [uv](https://github.com/astral-sh/uv)（Python 包管理）
- Node.js 18+（前端开发）
- Git

### 安装

```bash
git clone https://github.com/ADchampion3/CompSynth.git
cd CompSynth

# 后端依赖
uv sync

# 安装为可编辑包（可选，省去 uv run 前缀）
uv pip install -e .

# 前端依赖
cd frontend && npm install
```

### 环境配置

```bash
cp .env.example .env
# 编辑 .env，填入 LLM API Key 等配置

cp subscriptions.example.yaml subscriptions.yaml
# 编辑 subscriptions.yaml，添加你的订阅源
```

## 开发命令

| 命令 | 说明 |
|------|------|
| `compsynth serve` | 启动后端 API（默认 http://127.0.0.1:8000） |
| `cd frontend && npm run dev` | 启动前端开发服务器（默认 http://localhost:5173） |
| `compsynth doctor` | 检查环境配置是否正确 |
| `compsynth status` | 查看系统健康状态 |

## 测试

```bash
# 运行全部测试
uv run python -m pytest -q

# 运行单个测试文件
uv run python -m pytest tests/test_cli.py

# 编译检查
uv run python -m compileall -q src tests

# 带覆盖率
uv run python -m pytest --cov=src --cov-report=term-missing -q
```

### 测试标记

```bash
# 跳过需要 LLM 的测试
uv run python -m pytest -m "not allow_llm"

# 只运行慢速集成测试
uv run python -m pytest -m slow
```

### 编写测试

- 新功能必须有测试覆盖
- 使用 `tmp_path` fixture 创建临时目录
- 使用 `:memory:` SQLite 或 `tmp_path` 隔离数据库
- Mock 外部 API 调用（LLM、SMTP）
- 测试文件命名：`tests/test_<module>.py`

## 代码风格

- 遵循 PEP 8
- 使用 type annotations
- 格式化工具：black、isort、ruff（通过 pre-commit 自动运行）

### Pre-commit hooks

```bash
# 安装 hooks（首次）
uv run pre-commit install

# 手动运行所有 hooks
uv run pre-commit run --all-files
```

hooks 在每次 `git commit` 时自动运行，检查：
- 尾部空白、文件末尾换行
- YAML 语法
- Python AST
- 大文件
- isort（import 排序）
- ruff（lint）

## 提交流程

1. 从 `develop` 创建特性分支：`git checkout -b feature/my-feature`
2. 编写代码和测试
3. 确保测试通过：`uv run python -m pytest -q`
4. 提交（pre-commit hooks 自动检查）
5. 推送并创建 Pull Request

### 提交消息格式

```
<type>: <description>

类型：feat, fix, refactor, docs, test, chore, perf, ci
```

示例：
- `feat: add compsynth sources list CLI command`
- `fix: prevent sensitive variable leakage in stack traces`
- `docs: update environment variable reference`

## 项目结构

```
src/comp_synth/
  cli/          — Typer CLI 入口和命令定义
  api/          — FastAPI 应用、路由、schema
  services/     — 业务逻辑层
  store/        — SQLAlchemy 模型、仓储、迁移
  crawlers/     — RSS/Web/JS 爬虫实现
  orchestration/ — 管道节点和内容管理
  llm_provider/ — LLM 提供商注册
  publishers/   — 通知推送（邮件等）
  schema/       — Pydantic 数据模型
  utils/        — 工具函数（日志、限速、JSON 提取）
tests/          — 测试文件
frontend/       — React + TypeScript 前端
```

## 常见问题

### 测试因网络超时失败

检查 `COMPSYNTH_REQUEST_TIMEOUT` 设置，或标记为 `@pytest.mark.slow`。

### pre-commit hooks 安装失败

```bash
uv run pre-commit clean
uv run pre-commit install
```

### SQLite 数据库锁定

确保没有其他 compsynth 进程在运行。开发时可使用 `--db-path` 指定独立数据库。
