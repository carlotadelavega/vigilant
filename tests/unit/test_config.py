import pytest

from vigilant.config import Settings


def test_settings_defaults() -> None:
    """Settings should fall back to documented defaults when no env vars are set."""
    settings = Settings()

    assert settings.project_name == "VIGILANT"
    assert settings.api_v1_prefix == "/v1"
    assert settings.default_llm_model == "llama3.1"


def test_settings_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    """Environment variables should override the default settings values."""
    monkeypatch.setenv("DEFAULT_LLM_MODEL", "mistral")

    settings = Settings()

    assert settings.default_llm_model == "mistral"


def test_settings_ignores_unknown_env_vars(monkeypatch: pytest.MonkeyPatch) -> None:
    """Unknown environment variables must not raise, per extra='ignore'."""
    monkeypatch.setenv("SOME_UNRELATED_VAR", "irrelevant")

    settings = Settings()

    assert not hasattr(settings, "some_unrelated_var")
