"""zone sensors

Sensor de zonas inseguras (patente NC2025/0015763, SIMULADO): dispositivos, credenciales RFID
autorizadas y eventos (specs/004-zone-sensor).

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-21 10:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from geoalchemy2 import Geometry

from alembic import op

revision: str = "0005"
down_revision: str | Sequence[str] | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _enum(name: str, *values: str) -> sa.Enum:
    return sa.Enum(*values, name=name, native_enum=False, create_constraint=True, length=32)


def _common() -> list[sa.Column]:
    return [
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("source", sa.String(64), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "zone_sensors",
        *_common(),
        sa.Column("code", sa.String(32), nullable=False, unique=True),
        sa.Column("label", sa.String(120), nullable=False),
        sa.Column("geom", Geometry(geometry_type="POINT", srid=4326), nullable=False),
        sa.Column("heading_deg", sa.Float(), nullable=False),
        sa.Column("range_m", sa.Float(), nullable=False),
        sa.Column("half_angle_deg", sa.Float(), nullable=False),
        sa.Column("incident_id", sa.UUID(), nullable=True),
        sa.Column("status", _enum("zone_sensor_status", "armado", "desarmado"), nullable=False),
        sa.Column("battery_pct", sa.SmallInteger(), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_table(
        "rfid_badges",
        *_common(),
        sa.Column("tag", sa.String(32), nullable=False, unique=True),
        sa.Column("agency_code", sa.String(32), nullable=False),
        sa.Column("role_label", sa.String(80), nullable=False),
    )
    op.create_table(
        "zone_sensor_events",
        *_common(),
        sa.Column("sensor_id", sa.UUID(), sa.ForeignKey("zone_sensors.id"), nullable=False),
        sa.Column(
            "kind",
            _enum(
                "zone_event_kind", "intrusion", "acceso_autorizado", "bateria_baja", "manipulacion"
            ),
            nullable=False,
        ),
        sa.Column(
            "detector", _enum("zone_detector", "ultrasonido", "infrarrojo", "ambos"), nullable=True
        ),
        sa.Column("distance_m", sa.Float(), nullable=True),
        sa.Column("bearing_deg", sa.Float(), nullable=True),
        sa.Column("rfid_tag", sa.String(32), nullable=True),
        sa.Column("authorized", sa.Boolean(), nullable=False),
        sa.Column("battery_pct", sa.SmallInteger(), nullable=True),
        sa.Column("at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("acknowledged_by", sa.String(32), nullable=True),
    )
    op.create_index("ix_zone_sensor_events_at", "zone_sensor_events", ["at"])


def downgrade() -> None:
    op.drop_index("ix_zone_sensor_events_at", table_name="zone_sensor_events")
    op.drop_table("zone_sensor_events")
    op.drop_table("rfid_badges")
    op.drop_table("zone_sensors")
