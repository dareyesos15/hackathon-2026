"""Autenticación por token fijo por rol (research R9). Sin Keycloak en el prototipo."""

from collections.abc import Callable, Coroutine
from typing import Any

from fastapi import Depends, HTTPException, Query, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import get_settings
from app.domain import Role

_bearer = HTTPBearer(auto_error=False)


def _role_for(token: str | None) -> Role | None:
    if not token:
        return None
    role = get_settings().role_tokens().get(token)
    return Role(role) if role else None


def require_role(
    *allowed: Role, allow_query_token: bool = False
) -> Callable[..., Coroutine[Any, Any, Role]]:
    """Dependencia que exige un token válido con uno de los roles permitidos.

    `allow_query_token` permite `?token=` (EventSource no envía cabeceras).
    """

    async def dependency(
        creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
        token: str | None = Query(default=None, include_in_schema=allow_query_token),
    ) -> Role:
        raw = creds.credentials if creds else (token if allow_query_token else None)
        role = _role_for(raw)
        if role is None:
            raise HTTPException(
                status.HTTP_401_UNAUTHORIZED,
                detail={"detail": "Token ausente o inválido", "code": "unauthorized"},
            )
        if allowed and role not in allowed:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                detail={"detail": "Su rol no tiene permiso para esta acción", "code": "forbidden"},
            )
        return role

    return dependency
