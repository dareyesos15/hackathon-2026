"""Usuarios de prueba de la demo (sin Keycloak; research R9).

Cada usuario entra con su nombre y la contraseña de demo (`DEMO_PASSWORD`) y recibe el token
fijo de su rol de API. `area` es la sección de la interfaz a la que entra:
- `pmu`: tablero situacional, despacho, alertas, cascada, zonas, KPI y recuperación;
- `agencia`: avisos y despachos de una agencia de respuesta (EMRE);
- `admin`: simulaciones de la demo.
La ciudadanía no inicia sesión: reporta y ve el tablero público como anónima.
Todos los usuarios son ficticios: ningún nombre corresponde a una persona real.
"""

from __future__ import annotations

import hmac
from dataclasses import dataclass
from typing import Literal

from app.config import get_settings
from app.domain import Role

Area = Literal["pmu", "agencia", "admin"]


@dataclass(frozen=True)
class DemoUser:
    username: str
    display_name: str
    organization: str
    area: Area
    role: Role
    agency_code: str | None = None


DEMO_USERS: tuple[DemoUser, ...] = (
    DemoUser(
        "coe",
        "Coordinación COE",
        "UGR Manizales · Comité Operativo de Emergencias",
        "pmu",
        Role.coe,
    ),
    DemoUser("pmu", "Operación PMU", "Puesto de Mando Unificado", "pmu", Role.operador_pmu),
    DemoUser(
        "bomberos",
        "Central de Bomberos",
        "Cuerpo Oficial de Bomberos",
        "agencia",
        Role.agencia,
        "BOMBEROS",
    ),
    DemoUser(
        "cruzroja",
        "Central Cruz Roja",
        "Cruz Roja Colombiana",
        "agencia",
        Role.agencia,
        "CRUZ_ROJA",
    ),
    DemoUser(
        "defensacivil",
        "Central Defensa Civil",
        "Defensa Civil Colombiana",
        "agencia",
        Role.agencia,
        "DEFENSA_CIVIL",
    ),
    DemoUser(
        "infraestructura",
        "Central Infraestructura",
        "Secretaría de Infraestructura",
        "agencia",
        Role.agencia,
        "SEC_INFRAESTRUCTURA",
    ),
    DemoUser("admin", "Administración de la demo", "Equipo Dacora", "admin", Role.admin),
)

_BY_NAME = {u.username: u for u in DEMO_USERS}


def authenticate(username: str, password: str) -> DemoUser | None:
    user = _BY_NAME.get(username.strip().lower())
    expected = get_settings().demo_password
    ok = hmac.compare_digest(password.encode(), expected.encode())
    return user if user and ok else None


def token_for(role: Role) -> str:
    for token, name in get_settings().role_tokens().items():
        if name == role.value:
            return token
    raise LookupError(f"sin token para el rol {role}")
