"""报告格式检查器 — 验证 Markdown 报告格式是否规范."""

import re


class ReportFormatChecker:
    """检查 Markdown 报告格式是否符合规范（不阻断，仅警告）"""

    def __init__(self, report: str):
        self.report = report
        self.errors: list[str] = []
        self.warnings: list[str] = []

    def check_all(self) -> dict:
        """执行所有检查项"""
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

    def check_heading_hierarchy(self) -> None:
        """验证标题层级严格遵循 # -> ## -> ###，不得跳级"""
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
        emoji_pattern = re.compile(
            "[\U0001F300-\U0001F9FF"
            "\U0001FA00-\U0001FAFF"
            "☀-⛿"
            "✀-➿]"
        )
        emojis = emoji_pattern.findall(self.report)
        if len(emojis) > 15:
            self.warnings.append(
                f"emoji 数量为 {len(emojis)}，超过建议上限 15 个"
            )

    def check_link_format(self) -> None:
        """验证所有链接为 [text](url) 标准格式，不含裸 URL"""
        lines = self.report.split("\n")
        in_code_block = False
        for line in lines:
            if line.strip().startswith("```"):
                in_code_block = not in_code_block
                continue
            if in_code_block:
                continue
            bare_urls = re.findall(r"(?<!\[[^\]])\bhttps?://\S+", line)
            for url in bare_urls:
                if url not in self.report:
                    continue
                self.warnings.append(f"发现裸 URL: {url}，应使用 [标题](URL) 格式")

    def check_article_list_format(self) -> None:
        """验证文章列表格式：1. **[标题](URL)** - 摘要"""
        for line in self.report.split("\n"):
            stripped = line.strip()
            m = re.match(r"^\d+\.\s+", stripped)
            if m and "**[" in stripped:
                if not re.search(r"\*\*\[.+?\]\(.+?\)\*\*", stripped):
                    self.warnings.append(
                        f"文章列表格式可能不正确: '{stripped[:80]}'"
                    )

    def check_empty_lines(self) -> None:
        """验证模块间有空行分隔（简化检查：标题后紧跟非空行内容）"""
        lines = self.report.split("\n")
        for i, line in enumerate(lines):
            m = re.match(r"^(#{1,3})\s+", line.strip())
            if m and i + 1 < len(lines):
                next_line = lines[i + 1].strip()
                if next_line and not next_line.startswith("#"):
                    self.warnings.append(
                        f"标题 '{line.strip()}' 后缺少空行分隔，建议在标题与内容间加空行"
                    )
