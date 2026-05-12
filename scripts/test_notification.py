"""Integration test for notification publishers.

Runs outside pytest — call directly:
    uv run python scripts/test_notification.py                         # sample report
    uv run python scripts/test_notification.py output/digest_xxx.md   # real report
"""

import asyncio
import sys
from pathlib import Path

from comp_synth.config import settings
from comp_synth.publishers.email import EmailPublisher

SAMPLE_REPORT = """\
# CompSynth 日报 2026-05-12

## 主题 1: 测试推送

- 这是一条集成测试消息
- 如果你看到了，说明推送通道正常

## 主题 2: Markdown 渲染

> 引用块测试

| 项目 | 状态 |
|------|------|
| 邮件 | ✅ |
"""


async def main() -> None:
    channels = settings.get_channels()
    if not channels:
        print("未配置通知渠道。设置 COMPSYNTH_NOTIFICATION_CHANNELS=email 后重试")
        sys.exit(1)

    if len(sys.argv) > 1:
        report_path = Path(sys.argv[1])
        if not report_path.exists():
            print(f"文件不存在: {report_path}")
            sys.exit(1)
        report = report_path.read_text(encoding="utf-8")
        print(f"发送文件: {report_path} ({len(report)} 字符)\n")
    else:
        report = SAMPLE_REPORT
        print("发送示例报告\n")

    print(f"测试渠道: {', '.join(channels)}\n")

    for ch in channels:
        if ch == "email":
            pub = EmailPublisher()
            config = {
                "smtp_host": settings.smtp_host,
                "smtp_port": settings.smtp_port,
                "smtp_user": settings.smtp_user,
                "smtp_password": settings.smtp_password,
                "smtp_from": settings.smtp_from,
                "smtp_to": settings.smtp_to,
                "smtp_use_tls": settings.smtp_use_tls,
            }
        else:
            print(f"[{ch}] 未知渠道，跳过")
            continue

        result = await pub.publish(report, config)
        status = result["status"]
        error = result.get("error", "")
        details = result.get("details", "")

        if status == "success":
            print(f"[{ch}] OK - pushed {details}")
        elif status == "skipped":
            print(f"[{ch}] SKIP: {error}")
        else:
            print(f"[{ch}] FAIL: {error}")


if __name__ == "__main__":
    asyncio.run(main())
