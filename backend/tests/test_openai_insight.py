from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from src.ai.openai_client import enhance_with_openai, generate_insight
from src.config import get_settings


def _fake_settings(**overrides):
    settings = get_settings()
    return settings.model_copy(update=overrides)


def test_generate_insight_returns_text_on_success():
    fake_response = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content="  生成された要約文  "))]
    )
    fake_client = MagicMock()
    fake_client.chat.completions.create.return_value = fake_response

    with patch("openai.OpenAI", return_value=fake_client):
        result = generate_insight("dummy prompt", "sk-fake", "gpt-4o-mini")

    assert result == "生成された要約文"  # stripped
    fake_client.chat.completions.create.assert_called_once()


def test_generate_insight_returns_none_on_failure():
    with patch("openai.OpenAI", side_effect=RuntimeError("network error")):
        result = generate_insight("dummy prompt", "sk-fake", "gpt-4o-mini")

    assert result is None


def test_enhance_with_openai_stays_template_when_key_unset():
    settings = _fake_settings(openai_api_key=None)
    text, generated_by = enhance_with_openai("template sentence", "prompt", settings)

    assert text == "template sentence"
    assert generated_by == "template"


def test_enhance_with_openai_upgrades_to_openai_on_success():
    settings = _fake_settings(openai_api_key="sk-fake")

    with patch("src.ai.openai_client.generate_insight", return_value="OpenAIが生成した文"):
        text, generated_by = enhance_with_openai("template sentence", "prompt", settings)

    assert text == "OpenAIが生成した文"
    assert generated_by == "openai"


def test_enhance_with_openai_falls_back_to_template_on_failure():
    """Key is set but the call fails (e.g. invalid key, network error, rate
    limit) — must fall back to the template sentence and never label it
    "openai", matching this project's "never mislabel a demo/fallback
    result as real" principle."""
    settings = _fake_settings(openai_api_key="sk-fake")

    with patch("src.ai.openai_client.generate_insight", return_value=None):
        text, generated_by = enhance_with_openai("template sentence", "prompt", settings)

    assert text == "template sentence"
    assert generated_by == "template"


def test_churn_service_upgrades_ai_insight_when_openai_succeeds(dataset):
    """End-to-end through a real service: with OPENAI_API_KEY set and the
    OpenAI call mocked to succeed, churn_service.prepare() should produce
    ai_insight_generated_by="openai" with the mocked text — proving the
    service layer is actually wired to enhance_with_openai, not just the
    helper function in isolation."""
    from src.services import churn_service

    settings = _fake_settings(openai_api_key="sk-fake")

    with (
        patch("src.services.churn_service.get_settings", return_value=settings),
        patch("src.ai.openai_client.generate_insight", return_value="OpenAI生成の解約予測サマリー"),
    ):
        state = churn_service.prepare(dataset)

    assert state.ai_insight_generated_by == "openai"
    assert state.ai_insight == "OpenAI生成の解約予測サマリー"


def test_churn_service_falls_back_to_template_when_openai_fails(dataset):
    from src.services import churn_service

    settings = _fake_settings(openai_api_key="sk-fake")

    with (
        patch("src.services.churn_service.get_settings", return_value=settings),
        patch("src.ai.openai_client.generate_insight", return_value=None),
    ):
        state = churn_service.prepare(dataset)

    assert state.ai_insight_generated_by == "template"
    assert "AUC" in state.ai_insight  # still the real template sentence, not empty/broken
