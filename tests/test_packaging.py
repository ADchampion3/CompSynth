import importlib
import tomllib
from pathlib import Path


def test_package_imports_from_repo_root():
    assert importlib.import_module("comp_synth")


def test_console_script_points_to_existing_main():
    pyproject = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))

    assert pyproject["project"]["scripts"]["compsynth"] == "comp_synth.main:main"
    module_name, function_name = pyproject["project"]["scripts"]["compsynth"].split(":")
    module = importlib.import_module(module_name)

    assert callable(getattr(module, function_name))
