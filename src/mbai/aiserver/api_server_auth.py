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
import base64
import logging

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt

from mbai.aiserver.config import settings

logger = logging.getLogger(__name__)


# SECRET_KEY = "a90f53fac68d7a30285ba3f7e710f626b5c63112b0864f7b1d3c47bcb7555432"
# ALGORITHM = "HS256"
# AUDIENCE = "http://fabidemoclouddevel.sq.fabasoft.com:9000"

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


# Dependency to require a valid JWT
def jwt_required(token: str = Depends(oauth2_scheme)):
    """validation of json-web-token"""
    try:
        secret_decoded = base64.b64decode(settings.jwt_secret_key)
        payload = jwt.decode(
            token,
            secret_decoded,
            algorithms=[settings.jwt_algorithm],
            audience=settings.jwt_audience,
        )
        return payload
    except JWTError as e:
        logger.info(e)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )
