import pytest

from clauseproof import __main__ as cli
from clauseproof.config import ConfigError, load_settings


def test_settings_require_env(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_MODEL", raising=False)
    with pytest.raises(ConfigError, match="ANTHROPIC_API_KEY"):
        load_settings()


def test_settings_read_env(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "k")
    monkeypatch.setenv("ANTHROPIC_MODEL", "m")
    s = load_settings()
    assert (s.api_key, s.model) == ("k", "m")


def test_cli_rejects_short_file(tmp_path, capsys):
    f = tmp_path / "s.txt"
    f.write_text("tiny")
    assert cli.main(["analyze", str(f)]) == cli.EXIT_INPUT
    assert "Text too short" in capsys.readouterr().err


def test_cli_reports_missing_config(tmp_path, sample_dpa, monkeypatch, capsys):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_MODEL", raising=False)
    f = tmp_path / "d.txt"
    f.write_text(sample_dpa)
    assert cli.main(["analyze", str(f)]) == cli.EXIT_CONFIG
    assert "Configuration error" in capsys.readouterr().err
