"""mass alerts

Alerta masiva de toda la ciudad: sesión de operación propia (triaje, cascada y zonas) y reporte
final de problemas, trazabilidad y tiempos de solución.

Revision ID: 0006
Revises: 0005
Create Date: 2026-11-21 12:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision: str = "0006"
down_revision: str | Sequence[str] | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ROLES = ("ciudadano", "operador_pmu", "publico", "coe", "inspector", "agencia", "sistema", "admin")


def _enum(name: str, *values: str) -> sa.Enum:
    return sa.Enum(*values, name=name, native_enum=False, create_constraint=True, length=32)


def upgrade() -> None:
    op.create_table(
        "mass_alerts",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("source", sa.String(64), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(120), nullable=False),
        sa.Column(
            "event_type",
            _enum(
                "mass_alert_event",
                "sismo",
                "deslizamientos",
                "inundacion",
                "ceniza_volcanica",
                "incendio_estructural",
                "otro",
            ),
            nullable=False,
        ),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", _enum("mass_alert_status", "activa", "resuelta"), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by_role", _enum("mass_alert_created_by", *ROLES), nullable=False),
        sa.Column(
            "official_alert_id",
            sa.UUID(),
            sa.ForeignKey("alerts.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("final_report", JSONB(), nullable=True),
        sa.CheckConstraint("char_length(title) BETWEEN 1 AND 120", name="ck_mass_alert_title_len"),
        sa.CheckConstraint(
            "created_by_role IN ('operador_pmu', 'coe')", name="ck_mass_alert_created_by_role"
        ),
    )
    op.create_index(
        "uq_mass_alert_active",
        "mass_alerts",
        ["status"],
        unique=True,
        postgresql_where=sa.text("status = 'activa'"),
    )
    op.add_column(
        "incidents",
        sa.Column("mass_alert_id", sa.UUID(), sa.ForeignKey("mass_alerts.id"), nullable=True),
    )
    op.create_index("ix_incidents_mass_alert", "incidents", ["mass_alert_id"])


def downgrade() -> None:
    op.drop_index("ix_incidents_mass_alert", table_name="incidents")
    op.drop_column("incidents", "mass_alert_id")
    op.drop_index("uq_mass_alert_active", table_name="mass_alerts")
    op.drop_table("mass_alerts")
