"""recovery

Recuperación post-sismo: evaluaciones de habitabilidad, censo único, vulnerabilidad (tabla
separada), ayudas y albergues (specs/003-recovery).

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-21 09:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from geoalchemy2 import Geometry

from alembic import op

revision: str = "0004"
down_revision: str | Sequence[str] | None = "0003"
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
        "building_inspections",
        *_common(),
        sa.Column("property_id", sa.String(160), nullable=False),
        sa.Column("manzana_id", sa.String(16), sa.ForeignKey("manzanas.id"), nullable=True),
        sa.Column("color", _enum("inspection_color", "verde", "amarillo", "rojo"), nullable=False),
        sa.Column(
            "damage_level",
            _enum("damage_level", "menor", "mediano_uso_restringido", "mayor", "colapso"),
            nullable=False,
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("inspector_role", sa.String(32), nullable=False),
        sa.Column("at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_building_inspections_property", "building_inspections", ["property_id", "at"]
    )
    op.create_table(
        "households",
        *_common(),
        sa.Column("household_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("members_count", sa.SmallInteger(), nullable=False),
        sa.Column("property_id", sa.String(160), nullable=True),
        sa.Column("manzana_id", sa.String(16), sa.ForeignKey("manzanas.id"), nullable=True),
        sa.Column("rud_status", _enum("rud_status", "pendiente", "inscrito"), nullable=False),
        sa.Column("pets_count", sa.SmallInteger(), nullable=False, server_default="0"),
    )
    op.create_table(
        "household_vulnerability",
        sa.Column(
            "household_id",
            sa.UUID(),
            sa.ForeignKey("households.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("children", sa.Boolean(), nullable=False),
        sa.Column("elderly", sa.Boolean(), nullable=False),
        sa.Column("disability", sa.Boolean(), nullable=False),
        sa.Column("pregnancy", sa.Boolean(), nullable=False),
    )
    op.create_table(
        "aid_deliveries",
        *_common(),
        sa.Column("household_id", sa.UUID(), sa.ForeignKey("households.id"), nullable=False),
        sa.Column(
            "aid_type",
            _enum("aid_type", "subsidio_arriendo", "kit", "mercado", "albergue"),
            nullable=False,
        ),
        sa.Column("source_fund", sa.String(80), nullable=False),
        sa.Column("is_duplicate", sa.Boolean(), nullable=False),
        sa.Column("justification", sa.Text(), nullable=True),
        sa.Column("at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_aid_deliveries_household", "aid_deliveries", ["household_id", "aid_type", "at"]
    )
    op.create_table(
        "shelters",
        *_common(),
        sa.Column("code", sa.String(32), nullable=False, unique=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("barrio", sa.String(80), nullable=False),
        sa.Column("capacity", sa.Integer(), nullable=False),
        sa.Column("people", sa.Integer(), nullable=False),
        sa.Column("pets", sa.Integer(), nullable=False),
        sa.Column("geom", Geometry(geometry_type="POINT", srid=4326), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("people >= 0 AND people <= capacity", name="ck_shelter_capacity"),
        sa.CheckConstraint("pets >= 0", name="ck_shelter_pets"),
    )


def downgrade() -> None:
    op.drop_table("shelters")
    op.drop_index("ix_aid_deliveries_household", table_name="aid_deliveries")
    op.drop_table("aid_deliveries")
    op.drop_table("household_vulnerability")
    op.drop_table("households")
    op.drop_index("ix_building_inspections_property", table_name="building_inspections")
    op.drop_table("building_inspections")
