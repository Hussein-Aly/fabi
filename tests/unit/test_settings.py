from mbai.aiserver.config import settings


def test_settings_from_toml_keycloak():
    assert settings.llm_keycloak_token_url == "https://test.com/token"


def test_settings_from_toml_file_jwt():
    assert settings.jwt_secret_key == "test-secret-jwt-key"
