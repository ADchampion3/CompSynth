import pytest

from comp_synth.services.report_service import ReportService


def test_list_reports_returns_digest_files_newest_first(tmp_path):
    (tmp_path / "digest_20260101.md").write_text("# Older\n", encoding="utf-8")
    (tmp_path / "notes.md").write_text("# Ignore\n", encoding="utf-8")
    (tmp_path / "digest_20260201.md").write_text("# Newer\n", encoding="utf-8")

    service = ReportService(output_dir=tmp_path)

    reports = service.list_reports()

    assert [report.report_id for report in reports] == [
        "digest_20260201",
        "digest_20260101",
    ]
    assert reports[0].title == "Digest 2026-02-01"


def test_get_report_reads_markdown_and_metadata(tmp_path):
    (tmp_path / "digest_20260201.md").write_text("# Daily Digest\nBody", encoding="utf-8")

    service = ReportService(output_dir=tmp_path)

    report = service.get_report("digest_20260201")

    assert report.report_id == "digest_20260201"
    assert report.title == "Digest 2026-02-01"
    assert report.markdown == "# Daily Digest\nBody"


def test_get_report_rejects_path_traversal(tmp_path):
    service = ReportService(output_dir=tmp_path)

    with pytest.raises(ValueError, match="Invalid report id"):
        service.get_report("../digest_20260201")


def test_get_report_raises_for_missing_digest(tmp_path):
    service = ReportService(output_dir=tmp_path)

    with pytest.raises(FileNotFoundError):
        service.get_report("digest_20260201")


def test_record_report_metadata_lists_database_reports(tmp_path):
    report_path = tmp_path / "custom_digest.md"
    report_path.write_text("# Saved Report\n", encoding="utf-8")
    service = ReportService(output_dir=tmp_path, report_db_path=tmp_path / "reports.db")

    service.record_report(
        report_id="digest_20260201",
        title="Daily Intelligence",
        markdown_path=report_path,
        filters={"sources": ["Example Feed"]},
    )

    reports = service.list_reports()
    assert [report.report_id for report in reports] == ["digest_20260201"]
    assert reports[0].title == "Daily Intelligence"
    assert reports[0].path == report_path


def test_get_report_reads_markdown_from_database_metadata_path(tmp_path):
    report_path = tmp_path / "nested" / "digest.md"
    report_path.parent.mkdir()
    report_path.write_text("# DB Digest\nBody", encoding="utf-8")
    service = ReportService(output_dir=tmp_path, report_db_path=tmp_path / "reports.db")
    service.record_report(
        report_id="digest_20260201",
        title="Daily Intelligence",
        markdown_path=report_path,
    )

    report = service.get_report("digest_20260201")

    assert report.title == "Daily Intelligence"
    assert report.path == report_path
    assert report.markdown == "# DB Digest\nBody"
