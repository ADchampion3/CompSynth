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


# --- notify CLI command ---


class TestNotifyCommand:
    def test_skips_when_no_channels(self):
        from comp_synth.main import main

        with patch("comp_synth.config.settings") as mock_settings, \
             patch("builtins.print") as mock_print:
            mock_settings.get_channels.return_value = []
            main(["notify"])
            output = mock_print.call_args[0][0]
            import json
            result = json.loads(output)
            assert result["status"] == "skipped"

    def test_errors_when_no_digest(self, tmp_path):
        from comp_synth.main import main

        with patch("comp_synth.config.settings") as mock_settings, \
             patch("builtins.print") as mock_print:
            mock_settings.get_channels.return_value = ["email"]
            mock_settings.output_dir = str(tmp_path / "no_output")
            main(["notify"])
            import json
            result = json.loads(mock_print.call_args[0][0])
            assert result["status"] == "error"
            assert "no digest" in result["error"]

    def test_sends_latest_digest(self, tmp_path):
        from comp_synth.main import main

        digest = tmp_path / "digest_20260513.md"
        digest.write_text("# Test Report", encoding="utf-8")

        mock_pub = EmailPublisher()
        with patch("comp_synth.config.settings") as mock_settings, \
             patch("comp_synth.publishers.registry.get_enabled_publishers",
                   return_value=[mock_pub]), \
             patch.object(mock_pub, "publish", new_callable=AsyncMock,
                          return_value={"status": "success", "details": {"to": "test@test.com"}}), \
             patch("builtins.print") as mock_print:
            mock_settings.get_channels.return_value = ["email"]
            mock_settings.output_dir = str(tmp_path)
            main(["notify"])
            import json
            result = json.loads(mock_print.call_args[0][0])
            assert result["status"] == "sent"
            assert str(digest) in result["source"]
            assert result["results"][0]["status"] == "success"

    def test_sends_specified_file(self, tmp_path):
        from comp_synth.main import main

        report_file = tmp_path / "custom.md"
        report_file.write_text("# Custom Report", encoding="utf-8")

        mock_pub = EmailPublisher()
        with patch("comp_synth.config.settings") as mock_settings, \
             patch("comp_synth.publishers.registry.get_enabled_publishers",
                   return_value=[mock_pub]), \
             patch.object(mock_pub, "publish", new_callable=AsyncMock,
                          return_value={"status": "success", "details": {"to": "test@test.com"}}), \
             patch("builtins.print") as mock_print:
            mock_settings.get_channels.return_value = ["email"]
            mock_settings.output_dir = str(tmp_path)
            main(["notify", "--file", str(report_file)])
            import json
            result = json.loads(mock_print.call_args[0][0])
            assert result["status"] == "sent"
            assert str(report_file) in result["source"]

    def test_errors_when_specified_file_missing(self, tmp_path):
        from comp_synth.main import main

        missing = tmp_path / "nonexistent.md"
        with patch("comp_synth.config.settings") as mock_settings, \
             patch("builtins.print") as mock_print:
            mock_settings.get_channels.return_value = ["email"]
            main(["notify", "--file", str(missing)])
            import json
            result = json.loads(mock_print.call_args[0][0])
            assert result["status"] == "error"
            assert "file not found" in result["error"]

    def test_errors_when_file_not_markdown(self, tmp_path):
        from comp_synth.main import main

        txt_file = tmp_path / "report.txt"
        txt_file.write_text("not markdown", encoding="utf-8")
        with patch("comp_synth.config.settings") as mock_settings, \
             patch("builtins.print") as mock_print:
            mock_settings.get_channels.return_value = ["email"]
            main(["notify", "--file", str(txt_file)])
            import json
            result = json.loads(mock_print.call_args[0][0])
            assert result["status"] == "error"
            assert "only .md files" in result["error"]
