from __future__ import annotations

import logging

from app.config import Settings


def test_default_non_secret_configuration() -> None:
    settings = Settings(_env_file=None)

    assert settings.app_env == "development"
    assert settings.aws_region == "us-east-1"
    assert settings.bedrock_model_id == "example-model-id"
    assert settings.github_token is None
    assert settings.github_webhook_secret is None


def test_environment_variables_override_defaults(monkeypatch) -> None:
    monkeypatch.setenv("APP_ENV", "testing")
    monkeypatch.setenv("GITHUB_TOKEN", "test-token")
    monkeypatch.setenv("GITHUB_WEBHOOK_SECRET", "test-webhook-secret")
    monkeypatch.setenv("AWS_REGION", "eu-west-1")
    monkeypatch.setenv("BEDROCK_MODEL_ID", "test-model")

    settings = Settings(_env_file=None)

    assert settings.app_env == "testing"
    assert settings.github_token is not None
    assert settings.github_token.get_secret_value() == "test-token"
    assert settings.github_webhook_secret is not None
    assert settings.github_webhook_secret.get_secret_value() == "test-webhook-secret"
    assert settings.aws_region == "eu-west-1"
    assert settings.bedrock_model_id == "test-model"


def test_secret_values_are_masked_in_string_and_logging(caplog) -> None:
    settings = Settings(
        _env_file=None,
        github_token="test-token",
        github_webhook_secret="test-webhook-secret",
    )

    with caplog.at_level(logging.INFO):
        logging.getLogger(__name__).info("settings=%s", settings)

    output = f"{settings} {settings!r} {caplog.text}"
    assert "test-token" not in output
    assert "test-webhook-secret" not in output
    assert "**********" in output


def test_settings_load_from_dotenv_file(tmp_path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "APP_ENV=local\n"
        "AWS_REGION=ap-south-1\n"
        "BEDROCK_MODEL_ID=local-model\n",
        encoding="utf-8",
    )

    settings = Settings(_env_file=env_file)

    assert settings.app_env == "local"
    assert settings.aws_region == "ap-south-1"
    assert settings.bedrock_model_id == "local-model"
