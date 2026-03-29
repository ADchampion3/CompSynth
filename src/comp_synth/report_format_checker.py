"""报告格式检查器 — 验证 Markdown 报告是否符合 REPORT_GENERATOR_PROMPT 规范."""

import re


class ReportFormatChecker:
    """检查 Markdown 报告格式是否符合规范（不阻断，仅警告）"""

    # 标准 emoji 列表（来自 REPORT_GENERATOR_PROMPT）
    STANDARD_EMOJIS = {
        "📊", "🤖", "💸", "📝", "✅", "⚠️", "🔍",
        "🚀", "💡", "📰", "📌", "🔥", "⭐", "🎯",
    }

    def __init__(self, report: str):
        self.report = report
        self.errors: list[str] = []
        self.warnings: list[str] = []

    def check_all(self) -> dict:
        """执行所有检查项"""
        self.check_header()
        self.check_required_sections()
        self.check_heading_hierarchy()
        self.check_emoji_count()
        self.check_link_format()
        self.check_article_list_format()
        self.check_empty_lines()
        return {
            "passed": len(self.errors) == 0,
            "errors": self.errors,
            "warnings": self.warnings,
        }

    # ------------------------------------------------------------------
    # 各项检查
    # ------------------------------------------------------------------

    def check_header(self) -> None:
        """验证报告头部格式：`# 主题内容报告 - YYYY-MM-DD`"""
        pattern = r"^#\s+主题内容报告\s+-\s+\d{4}-\d{2}-\d{2}\s*$"
        for line in self.report.split("\n"):
            line = line.strip()
            if line.startswith("#"):
                if not re.match(pattern, line):
                    self.errors.append(
                        f"报告头部格式错误: '{line}'，期望格式: '# 主题内容报告 - YYYY-MM-DD'"
                    )
                break
        else:
            self.errors.append("报告缺少一级标题（格式: # 主题内容报告 - YYYY-MM-DD）")

    def check_required_sections(self) -> None:
        """验证必含章节：核心总览 📊、结语与延伸推荐 🔍"""
        if "## 核心总览" not in self.report and "## 核心总览 📊" not in self.report:
            self.errors.append("报告缺少必含章节: '## 核心总览 📊'")
        if "## 结语与延伸推荐" not in self.report and "## 结语与延伸推荐 🔍" not in self.report:
            self.errors.append("报告缺少必含章节: '## 结语与延伸推荐 🔍'")

    def check_heading_hierarchy(self) -> None:
        """验证标题层级严格遵循 # → ## → ###，不得跳级"""
        lines = self.report.split("\n")
        prev_level = 0
        for line in lines:
            m = re.match(r"^(#{1,6})\s+", line.strip())
            if m:
                level = len(m.group(1))
                if level > prev_level + 1 and prev_level > 0:
                    self.errors.append(
                        f"标题层级跳级: {'#' * prev_level} 后直接使用 {'#' * level}，"
                        f"层级应严格递增（当前行: '{line.strip()}'）"
                    )
                prev_level = level

    def check_emoji_count(self) -> None:
        """验证单篇报告 emoji 总量不超过 15 个"""
        # 匹配常见 emoji（包括 unicode emoji 范围）
        emoji_pattern = re.compile(
            "[\U0001F300-\U0001F9FF"
            "\U0001FA00-\U0001FAFF"
            "\u2600-\u26FF"
            "\u2700-\u27BF]"
        )
        emojis = emoji_pattern.findall(self.report)
        if len(emojis) > 15:
            self.warnings.append(
                f"emoji 数量为 {len(emojis)}，超过建议上限 15 个"
            )

    def check_link_format(self) -> None:
        """验证所有链接为 [text](url) 标准格式，不含裸 URL"""
        # 排除代码块内的 URL
        lines = self.report.split("\n")
        in_code_block = False
        for line in lines:
            if line.strip().startswith("```"):
                in_code_block = not in_code_block
                continue
            if in_code_block:
                continue
            # 裸 URL 检测（行内出现非 Markdown 链接的 http(s)://）
            bare_urls = re.findall(r"(?<!\[[^\]])\bhttps?://\S+", line)
            for url in bare_urls:
                # 排除已经是 [text](url) 格式的
                if url not in self.report:
                    continue
                self.warnings.append(f"发现裸 URL: {url}，应使用 [标题](URL) 格式")

    def check_article_list_format(self) -> None:
        """验证文章列表格式：1. ✅ **[标题](URL)** - 摘要 或 1. ⚠️ ..."""
        article_lines = []
        for line in self.report.split("\n"):
            stripped = line.strip()
            # 匹配文章列表项
            m = re.match(r"^\d+\.\s*([✅⚠️])\s+\*\*\[", stripped)
            if m:
                article_lines.append((stripped, m.group(1)))
        # 检查 ⚠️ 条是否都在末尾
        for i, (line, status) in enumerate(article_lines):
            if status == "⚠️":
                # 检查后面是否还有 ✅
                later_oks = [s for _, s in article_lines[i + 1 :]]
                if "✅" in later_oks:
                    self.warnings.append(
                        f"⚠️ 标记的解析失败条目未放在主题列表末尾: '{line}'"
                    )

    def check_empty_lines(self) -> None:
        """验证模块间有空行分隔（简化检查：标题后紧跟非空行内容）"""
        lines = self.report.split("\n")
        for i, line in enumerate(lines):
            m = re.match(r"^(#{1,3})\s+", line.strip())
            if m and i + 1 < len(lines):
                next_line = lines[i + 1].strip()
                if next_line and not next_line.startswith("#"):
                    # 标题后紧跟内容，警告（可能缺少空行）
                    self.warnings.append(
                        f"标题 '{line.strip()}' 后缺少空行分隔，建议在标题与内容间加空行"
                    )
