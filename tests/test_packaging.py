import importlib
import tomllib
from pathlib import Path


def test_package_imports_from_repo_root():
    assert importlib.import_module("comp_synth")


def test_console_script_points_to_existing_main():
    pyproject = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))

    entry_point = pyproject["project"]["scripts"]["compsynth"]
    module_name, attr_name = entry_point.split(":")
    module = importlib.import_module(module_name)

    assert callable(getattr(module, attr_name))


def test_project_description_is_readable_chinese():
    pyproject = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))

    assert pyproject["project"]["description"] == "内容聚合与发布系统 - 自动订阅、整合分析、媒体推送"
