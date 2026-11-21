"""The local .env loader used by dev settings (Docker passes .env itself)."""

import os

from config.settings.dotenv import load_dotenv


def test_loads_values_without_overriding_real_env(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text(
        "# comment\n\nLP_A=one\nexport LP_B='two words'\nLP_C=\"x=y\"\nLP_EMPTY=\nLP_SET=from-file\n",
        encoding="utf-8",
    )
    for key in ("LP_A", "LP_B", "LP_C", "LP_EMPTY"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("LP_SET", "from-env")

    load_dotenv(env)

    assert os.environ["LP_A"] == "one"
    assert os.environ["LP_B"] == "two words"
    assert os.environ["LP_C"] == "x=y"
    assert os.environ["LP_EMPTY"] == ""
    assert os.environ["LP_SET"] == "from-env"  # real env vars win
    for key in ("LP_A", "LP_B", "LP_C", "LP_EMPTY"):
        monkeypatch.delenv(key)


def test_missing_file_is_ignored(tmp_path):
    load_dotenv(tmp_path / "nope.env")
