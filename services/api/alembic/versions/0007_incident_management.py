"""incident management

Gestión de incidentes del PMU/COE: varias alertas masivas activas a la vez, bandeja de incidentes
sin asignar y acciones manuales en la bitácora (crear, asignar y desacoplar de una alerta).

Revision ID: 0007
Revises: 0006
Create Date: 2026-11-21 14:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0007"
down_revision: str | Sequence[str] | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

BASE_ACTIONS = (
    "ingerido",
    "agrupado",
    "confirmar",
    "descartar",
    "marcar_duplicado",
    "reabrir",
    "despachar",
    "reforzar",
    "despacho_estado",
    "cancelar_despacho",
    "despacho_doble_bloqueado",
    "cerrar_atendido",
)
NEW_ACTIONS = ("crear_manual", "asignar_alerta", "desacoplar_alerta")


def _action_check(actions: tuple[str, ...]) -> str:
    return "action IN (" + ", ".join(f"'{a}'" for a in actions) + ")"


def upgrade() -> None:
    op.drop_index("uq_mass_alert_active", table_name="mass_alerts")
    op.create_index("ix_mass_alerts_status", "mass_alerts", ["status"])
    op.add_column(
        "incidents",
        sa.Column(
            "pending_assignment", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
    )
    op.drop_constraint("report_action", "report_events", type_="check")
    op.create_check_constraint(
        "report_action", "report_events", _action_check(BASE_ACTIONS + NEW_ACTIONS)
    )


def downgrade() -> None:
    op.execute(
        "DELETE FROM report_events WHERE action IN ("
        + ", ".join(f"'{a}'" for a in NEW_ACTIONS)
        + ")"
    )
    op.drop_constraint("report_action", "report_events", type_="check")
    op.create_check_constraint("report_action", "report_events", _action_check(BASE_ACTIONS))
    op.drop_column("incidents", "pending_assignment")
    op.drop_index("ix_mass_alerts_status", table_name="mass_alerts")
    op.create_index(
        "uq_mass_alert_active",
        "mass_alerts",
        ["status"],
        unique=True,
        postgresql_where=sa.text("status = 'activa'"),
    )
