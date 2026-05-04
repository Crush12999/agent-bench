from pathlib import Path

import tomllib

import agentbench


def test_project_metadata_and_version_are_defined():
    project_root = Path(__file__).resolve().parents[1]
    metadata = tomllib.loads((project_root / "pyproject.toml").read_text(encoding="utf-8"))

    assert metadata["project"]["name"] == "agentbench"
    assert metadata["project"]["version"] == agentbench.__version__
    assert metadata["project"]["scripts"]["agentbench"] == "agentbench.cli:main"
