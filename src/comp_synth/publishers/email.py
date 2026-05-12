import asyncio
import smtplib
from datetime import datetime
from email.header import Header
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr, formatdate, make_msgid

import markdown
from loguru import logger

from comp_synth.config import settings
from comp_synth.publishers.base import BasePublisher

# Auto-detect SMTP config by sender domain.
# use_starttls=True → SMTP + STARTTLS (port 587)
# use_starttls=False → SMTP_SSL (port 465)
SMTP_CONFIGS: dict[str, dict[str, object]] = {
    "gmail.com": {"server": "smtp.gmail.com", "port": 587, "use_starttls": True},
    "qq.com": {"server": "smtp.qq.com", "port": 465, "use_starttls": False},
    "outlook.com": {"server": "smtp-mail.outlook.com", "port": 587, "use_starttls": True},
    "hotmail.com": {"server": "smtp-mail.outlook.com", "port": 587, "use_starttls": True},
    "live.com": {"server": "smtp-mail.outlook.com", "port": 587, "use_starttls": True},
    "163.com": {"server": "smtp.163.com", "port": 465, "use_starttls": False},
    "126.com": {"server": "smtp.126.com", "port": 465, "use_starttls": False},
    "sina.com": {"server": "smtp.sina.com", "port": 465, "use_starttls": False},
    "sohu.com": {"server": "smtp.sohu.com", "port": 465, "use_starttls": False},
    "189.cn": {"server": "smtp.189.cn", "port": 465, "use_starttls": False},
    "aliyun.com": {"server": "smtp.aliyun.com", "port": 465, "use_starttls": True},
    "yandex.com": {"server": "smtp.yandex.com", "port": 465, "use_starttls": True},
    "icloud.com": {"server": "smtp.mail.me.com", "port": 587, "use_starttls": True},
}

_EMAIL_CSS = """\
body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,"Helvetica Neue",\
Arial,"PingFang SC","Microsoft YaHei",sans-serif;max-width:720px;margin:0 auto;\
padding:20px;line-height:1.7;color:#333;background:#fff}
table{border-collapse:collapse;width:100%;margin:16px 0}
th,td{border:1px solid #ddd;padding:8px 12px;text-align:left}
th{background:#f5f5f5;font-weight:600}
blockquote{border-left:4px solid #ddd;margin:16px 0;padding:8px 16px;color:#666}
code{background:#f4f4f4;padding:2px 6px;font-size:90%}
pre{background:#f4f4f4;padding:16px;overflow-x:auto;font-size:90%;line-height:1.5}
pre code{padding:0;background:none}
img{max-width:100%;height:auto}
h1,h2,h3{margin-top:24px;margin-bottom:12px}
a{color:#1a73e8}
"""


def _resolve_smtp(config: dict) -> tuple[str, int, bool]:
    if config.get("smtp_host"):
        port = config.get("smtp_port", 465)
        use_starttls = port == 587
        return config["smtp_host"], port, use_starttls

    from_addr = config.get("smtp_from", "")
    domain = from_addr.split("@")[-1].lower() if "@" in from_addr else ""
    if domain in SMTP_CONFIGS:
        cfg = SMTP_CONFIGS[domain]
        return cfg["server"], cfg["port"], cfg["use_starttls"]  # type: ignore[index]

    fallback = f"smtp.{domain}" if domain else ""
    return fallback, 587, True


def _send_smtp(
    smtp_host: str,
    smtp_port: int,
    use_starttls: bool,
    user: str,
    password: str,
    from_addr: str,
    to_addr: str,
    msg_bytes: bytes,
) -> None:
    if use_starttls:
        server = smtplib.SMTP(smtp_host, smtp_port, timeout=30)
        server.ehlo()
        server.starttls()
        server.ehlo()
    else:
        server = smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=30)
        server.ehlo()
    try:
        server.login(user, password)
        server.sendmail(from_addr, [to_addr], msg_bytes)
    finally:
        server.quit()


class EmailPublisher(BasePublisher):
    channel_name = "email"

    def get_config(self) -> dict:
        return {
            "smtp_host": settings.smtp_host,
            "smtp_port": settings.smtp_port,
            "smtp_user": settings.smtp_user,
            "smtp_password": settings.smtp_password,
            "smtp_from": settings.smtp_from,
            "smtp_to": settings.smtp_to,
            "smtp_use_tls": settings.smtp_use_tls,
        }

    async def publish(self, report: str, config: dict) -> dict:
        required = ("smtp_user", "smtp_password", "smtp_from", "smtp_to")
        missing = [k for k in required if not config.get(k)]
        if missing:
            return {"status": "skipped", "error": f"missing config: {', '.join(missing)}"}

        date_str = datetime.now().strftime("%Y-%m-%d")
        subject = f"CompSynth 日报 {date_str}"

        html_body = markdown.markdown(report, extensions=["tables", "fenced_code"])
        html = (
            "<!DOCTYPE html>\n<html><head><meta charset='utf-8'>"
            f"<style>{_EMAIL_CSS}</style></head><body>"
            + html_body +
            "</body></html>"
        )

        msg = MIMEMultipart("alternative")
        msg["From"] = formataddr(("CompSynth", config["smtp_from"]))
        msg["To"] = config["smtp_to"]
        msg["Subject"] = Header(subject, "utf-8")
        msg["MIME-Version"] = "1.0"
        msg["Date"] = formatdate(localtime=True)
        msg["Message-ID"] = make_msgid()
        msg.attach(MIMEText(report, "plain", "utf-8"))
        msg.attach(MIMEText(html, "html", "utf-8"))

        smtp_host, smtp_port, use_starttls = _resolve_smtp(config)

        if not smtp_host:
            return {"status": "error", "error": "could not resolve SMTP server"}

        try:
            await asyncio.to_thread(
                _send_smtp,
                smtp_host,
                smtp_port,
                use_starttls,
                config["smtp_user"],
                config["smtp_password"],
                config["smtp_from"],
                config["smtp_to"],
                msg.as_bytes(),
            )
            logger.info("Email notification sent to {}", config["smtp_to"])
            return {"status": "success", "details": {"to": config["smtp_to"]}}
        except Exception as e:
            logger.error("Email notification failed: {}", e)
            return {"status": "error", "error": str(e)}
