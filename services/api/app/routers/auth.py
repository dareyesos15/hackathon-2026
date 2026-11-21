"""Inicio de sesión de entidades y administrador con usuarios de prueba (app.core.users)."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.config import get_settings
from app.core.users import DEMO_USERS, authenticate, token_for

router = APIRouter(prefix="/auth", tags=["autenticación"])


class LoginIn(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=128)


class LoginOut(BaseModel):
    token: str
    area: Literal["pmu", "agencia", "admin"]
    api_role: str
    username: str
    display_name: str
    organization: str
    agency_code: str | None


class DemoUserOut(BaseModel):
    username: str
    display_name: str
    organization: str
    area: Literal["pmu", "agencia", "admin"]
    api_role: str


class DemoUserList(BaseModel):
    items: list[DemoUserOut]
    password_hint: str | None = Field(
        description="Contraseña de prueba; solo se publica en modo demo"
    )


@router.post("/login", response_model=LoginOut)
async def login(body: LoginIn) -> LoginOut:
    user = authenticate(body.username, body.password)
    if user is None:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            detail={"detail": "Usuario o contraseña incorrectos", "code": "invalid_credentials"},
        )
    return LoginOut(
        token=token_for(user.role),
        area=user.area,
        api_role=user.role.value,
        username=user.username,
        display_name=user.display_name,
        organization=user.organization,
        agency_code=user.agency_code,
    )


@router.get("/demo-users", response_model=DemoUserList)
async def demo_users() -> DemoUserList:
    """Usuarios de prueba para la pantalla de inicio de sesión (vacío fuera de modo demo)."""
    settings = get_settings()
    if not settings.demo_mode:
        return DemoUserList(items=[], password_hint=None)
    return DemoUserList(
        items=[
            DemoUserOut(
                username=u.username,
                display_name=u.display_name,
                organization=u.organization,
                area=u.area,
                api_role=u.role.value,
            )
            for u in DEMO_USERS
        ],
        password_hint=settings.demo_password,
    )
