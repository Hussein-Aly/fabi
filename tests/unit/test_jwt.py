import base64
from fastapi.exceptions import HTTPException
import pytest
from jose import jwt
from mbai.aiserver.config import settings

# from jose.exceptions import JWSSignatureError
import logging

logger = logging.getLogger(__name__)
token = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJpc3MiOiJodHRwczovL3NvbG9ibGl2YXRpb25tYi5zcS5mYWJhc29mdC5jb20vZm9saW8iLCJzdWIiOiJzY2h1bGxlcjAwMDFAc3EuZmFiYXNvZnQuY29tIiwiYXVkIjoiaHR0cDovL3NvbG9ibGl2YXRpb25tYi5zcS5mYWJhc29mdC5jb206OTAwMC9qd3RfdGVzdCIsImV4cCI6MTc1ODIwMTgxOSwibmJmIjoxNzU4MTg5ODE5LCJpYXQiOjE3NTgxODk4MTksImp0aSI6ImxvRk91WjF3Y2VoVno2NUplbUw4K1ZVYiIsInNjb3BlIjoiQ09PLjExMS4xMDAuMS4yMzA2MTY1In0.8uvVR4s1VhIocmm6PDBMfoBx7-pG_BN5H7EvEQhIzuU"
SECRET_KEY = "a90f53fac68d7a30285ba3f7e710f626b5c63112b0864f7b1d3c47bcb7555432"
secret_decoded = base64.b64decode(SECRET_KEY)
ALGORITHM = "HS256"
AUDIENCE = "http://soloblivationmb.sq.fabasoft.com:9000/jwt_test"


@pytest.fixture(autouse=True)
def reset_env_vars():
    """resets env vars after every test"""
    # note: placeholder for code before every test
    yield
    # note: placeholder for code after every test
    settings.reload()


def test_hardcoded():

    payload = jwt.decode(
        token,
        secret_decoded,
        algorithms=[ALGORITHM],
        audience=AUDIENCE,
        options={"verify_exp": False},
    )

    logger.info(payload)


def test_hardcoded_without_audience():

    payload = jwt.decode(
        token,
        secret_decoded,
        algorithms=[ALGORITHM],
        options={"verify_aud": False, "verify_exp": False},
    )

    logger.info(payload)


def test_jwt_function_enabled_jwt_wrong_settings(monkeypatch):

    with pytest.raises(ValueError, match=r".*validation error for Settings.*"):
        monkeypatch.setenv("jwt_enabled", True)
        monkeypatch.setenv("jwt_secret_key", "")
        settings.reload()
        from mbai.aiserver.api_server_auth import jwt_required

        jwt_required(token=token)


def test_jwt_function_enabled_jwt(monkeypatch):
    monkeypatch.setenv("jwt_enabled", True)
    monkeypatch.setenv("jwt_secret_key", SECRET_KEY)
    monkeypatch.setenv("jwt_algorithm", ALGORITHM)
    monkeypatch.setenv("jwt_audience", AUDIENCE)

    settings.reload()
    assert settings.jwt_secret_key == SECRET_KEY, "settings not set correctly"

    from mbai.aiserver.api_server_auth import jwt_required

    with pytest.raises(HTTPException, match=r".*Signature has expired.*"):
        jwt_required(token=token)
