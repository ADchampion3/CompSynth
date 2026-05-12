import asyncio
from unittest.mock import AsyncMock, patch

from comp_synth.publishers.email import EmailPublisher, _resolve_smtp
from comp_synth.publishers.registry import get_enabled_publishers, reset_registry

# --- Registry ---


class TestRegistry:
    def setup_method(self):
        reset_registry()

    def test_returns_email_publisher(self):
        pubs = get_enabled_publishers(["email"])
        assert len(pubs) == 1
        assert isinstance(pubs[0], EmailPublisher)

    def test_ignores_unknown_channels(self):
        pubs = get_enabled_publishers(["wechat", "telegram", "email"])
        assert len(pubs) == 1

    def test_empty_channels(self):
        pubs = get_enabled_publishers([])
        assert pubs == []


# --- Email ---


class TestResolveSmtp:
    def test_auto_detect_qq(self):
        host, port, use_tls = _resolve_smtp({"smtp_from": "user@qq.com"})
        assert host == "smtp.qq.com"
        assert port == 465
        assert use_tls is False

    def test_auto_detect_gmail(self):
        host, port, use_tls = _resolve_smtp({"smtp_from": "user@gmail.com"})
        assert host == "smtp.gmail.com"
        assert port == 587
        assert use_tls is True

    def test_custom_host_overrides(self):
        host, port, use_tls = _resolve_smtp({
            "smtp_host": "mail.example.com",
            "smtp_port": 25,
            "smtp_from": "user@example.com",
        })
        assert host == "mail.example.com"
        assert port == 25
        assert use_tls is False

    def test_auto_detect_163(self):
        host, port, use_tls = _resolve_smtp({"smtp_from": "user@163.com"})
        assert host == "smtp.163.com"
        assert port == 465
        assert use_tls is False


class TestEmailPublisher:
    def test_skips_when_missing_config(self):
        pub = EmailPublisher()
        result = asyncio.run(pub.publish("report", {"smtp_user": "", "smtp_password": ""}))
        assert result["status"] == "skipped"


# --- Notify node ---


class TestNotifyNode:
    def test_returns_empty_when_no_channels(self):
        from comp_synth.orchestration.nodes import notify

        state = {
            "report": "# Test Report",
            "publish_results": {"status": "success"},
        }
        with patch("comp_synth.orchestration.nodes.settings") as mock_settings:
            mock_settings.get_channels.return_value = []
            result = asyncio.run(notify(state))
        assert result["notification_results"] == []

    def test_returns_empty_when_report_empty(self):
        from comp_synth.orchestration.nodes import notify

        state = {
            "report": "",
            "publish_results": {"status": "success"},
        }
        result = asyncio.run(notify(state))
        assert result["notification_results"] == []

    def test_returns_empty_when_publish_skipped(self):
        from comp_synth.orchestration.nodes import notify

        state = {
            "report": "# Report",
            "publish_results": {"status": "skipped"},
        }
        result = asyncio.run(notify(state))
        assert result["notification_results"] == []


class TestNotifyErrorHandling:
    def test_records_error_when_publisher_fails(self):
        from comp_synth.orchestration.nodes import notify

        mock_pub = EmailPublisher()
        email_mock = AsyncMock(side_effect=Exception("SMTP error"))

        with patch.object(mock_pub, "publish", email_mock), \
             patch("comp_synth.publishers.registry.get_enabled_publishers",
                   return_value=[mock_pub]), \
             patch("comp_synth.orchestration.nodes.settings") as mock_settings:
            mock_settings.get_channels.return_value = ["email"]
            state = {
                "report": "# Report",
                "publish_results": {"status": "success"},
            }
            result = asyncio.run(notify(state))
            assert len(result["notification_results"]) == 1
            assert result["notification_results"][0]["status"] == "error"
