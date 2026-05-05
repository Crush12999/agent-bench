import os
from pathlib import Path

from agentbench.env import load_dotenv


def test_load_dotenv_ignores_missing_file(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    loaded = load_dotenv()

    assert loaded == []


def test_load_dotenv_loads_values_without_overriding_existing_env(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("EXISTING_KEY", "from-env")
    (tmp_path / ".env").write_text(
        """
# comment
JUDGE_API_KEY=from-file
EXISTING_KEY=from-file
EMPTY_LINE_TEST=value

""",
        encoding="utf-8",
    )

    loaded = load_dotenv()

    assert loaded == ["JUDGE_API_KEY", "EMPTY_LINE_TEST"]
    assert os.environ["JUDGE_API_KEY"] == "from-file"
    assert os.environ["EXISTING_KEY"] == "from-env"
    assert os.environ["EMPTY_LINE_TEST"] == "value"
