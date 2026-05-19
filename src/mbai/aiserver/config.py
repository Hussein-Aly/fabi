# ==========================================================================
# Copyright (c) Fabasoft R&D GmbH, A-4020 Linz, 1988-2026.
#
# Alle Rechte vorbehalten. Alle verwendeten Hard- und Softwarenamen sind
# Handelsnamen und/oder Marken der jeweiligen Hersteller.
#
# Der Nutzer des Computerprogramms anerkennt, dass der oben stehende
# Copyright-Vermerk im Sinn des Welturheberrechtsabkommens an der vom
# Urheber festgelegten Stelle in der Funktion des Computerprogramms
# angebracht bleibt, um den Vorbehalt des Urheberrechtes genuegend zum
# Ausdruck zu bringen. Dieser Urheberrechtsvermerk darf weder vom Kunden,
# Nutzer und/oder von Dritten entfernt, veraendert oder disloziert werden.
# ==========================================================================
import logging
import os

from mbai.base.model import MBConnectionValues, KeycloakValues
from pydantic import Field, model_validator
from pydantic_settings import BaseSettings

from mbai.telemetry.logging_config import configure_logging

# Setup Logging
configure_logging()

logger = logging.getLogger(__name__)
DOTENV = os.path.join(os.path.dirname(__file__), ".env")


class Settings(BaseSettings):
    # section: general base-ai-controller
    default_retries: int = Field(default=3, description="default retries for mb api calls")
    default_retry_waiting_time: int = Field(default=3, description="default retries for mb api calls")
    return_complete_stacktrace: bool = Field(default=False, description="return complete stacktrace on error")

    # section: general fast api
    fast_api_app_title: str = "AI Python Service: Fabi Chatbot"
    fast_api_app_description: str = "A detailed description of the API."

    fast_api_docs_enabled: bool = Field(default=False, description="enable api docs (disable in prod)")

    # section: test routes (jwt and connection tests)
    test_routes_enabled: bool = Field(default=False, description="enable test routes")

    # section: jwt (values from deployment)
    jwt_enabled: bool = Field(default=True, description="If True, disables JWT auth for dev-environment")
    jwt_secret_key: str | None = Field(None, description="secret key for JWT auth")
    jwt_algorithm: str = Field("HS256", description="algorithm for JWT auth")  # maybe set HS256 as default
    jwt_audience: str = Field("ai-python-service", description="audience for JWT auth")

    # section: mb connection values (mostly via deployment, only x_username dynamic)
    llm_keycloak_realm: str = Field()
    llm_keycloak_token_url: str = Field()
    llm_keycloak_client_id: str = Field()
    llm_keycloak_client_secret: str = Field()

    inspire_keycloak_realm: str = Field()
    inspire_keycloak_token_url: str = Field()
    inspire_keycloak_client_id: str = Field()
    inspire_keycloak_client_secret: str = Field()

    inspire_frontend_host: str
    inspire_backend_host: str
    inspire_backend_user: str = Field(default="admin", description="username for inspire_backend")
    inspire_backend_password: str = Field(default="Appliance123", description="username for inspire_backend")
    inspire_rag_service_id: str
    inspire_client_service_id: str

    # Agent Setup
    # mcp_url:str = Field(default="None", description="url for MCP server")

    # Telemetry
    otel_exporter: str = "langfuse"  # "jsonl" or "langfuse"
    otel_jsonl_path: str = "traces/traces.jsonl"
    otel_metrics_jsonl_path: str = "traces/metrics.jsonl"
    otel_metric_export_interval_ms: int = 60_000

    class Config:
        frozen = True  # read-only
        env_file = DOTENV
        env_file_encoding = "utf-8"

    @model_validator(mode="after")
    def check_jwt_requirements(self):
        if self.jwt_enabled and not self.jwt_secret_key:
            raise ValueError("jwt_secret_key must be set if jwt_enabled=True")
        return self

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        logger.info(f"Settings loaded: {self._safe_repr()}")

    def _safe_repr(self):
        """returns all env vars with secrets and passwords hidden, (just for logging)"""
        data = self.model_dump()
        safe_data = {}
        for key, value in data.items():
            if any(s in key.lower() for s in ["secret", "password", "key"]) and len(str(value)) >= 1:
                safe_data[key] = "*******"
            else:
                safe_data[key] = value
        return safe_data

    def reload(self):
        new = self.__class__()  # read env again
        self.__dict__.update(new.__dict__)


settings = Settings()


def build_mb_connection_values(x_username: str = "schuller0001@sq.fabasoft.com") -> MBConnectionValues:
    mb_conn_values = MBConnectionValues(
        inspire_frontend_host=settings.inspire_frontend_host,
        inspire_backend_host=settings.inspire_backend_host,
        inspire_backend_user=settings.inspire_backend_user,
        inspire_backend_password=settings.inspire_backend_password,
        x_username=x_username,
        inspire_rag_service_id=settings.inspire_rag_service_id,
        inspire_client_service_id=settings.inspire_client_service_id,
        inspire_keycloak=KeycloakValues(
            oauth_realm=settings.inspire_keycloak_realm,
            oauth_token_url=settings.inspire_keycloak_token_url,
            oauth_client_id=settings.inspire_keycloak_client_id,
            oauth_client_secret=settings.inspire_keycloak_client_secret,
        ),
        llm_keycloak=KeycloakValues(
            oauth_realm=settings.llm_keycloak_realm,
            oauth_token_url=settings.llm_keycloak_token_url,
            oauth_client_id=settings.llm_keycloak_client_id,
            oauth_client_secret=settings.llm_keycloak_client_secret,
        ),
    )
    return mb_conn_values
