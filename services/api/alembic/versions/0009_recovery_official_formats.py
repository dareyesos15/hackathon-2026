"""recovery official formats

Censo único con los campos del RUD (UNGRD), ayudas con el acta de entrega de ayuda humanitaria y
albergues con entidad administradora, estado y servicios (EMRE 3.1–3.3). La ocupación de cada
albergue sale de los hogares alojados (ayuda "albergue" sin fecha de salida).

Revision ID: 0009
Revises: 0008
Create Date: 2026-11-21 17:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0009"
down_revision: str | Sequence[str] | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ZERO = sa.text("0")
EMPTY = sa.text("'{}'")
COUNTS = ("age_0_5", "age_6_17", "age_18_59", "age_60_plus", "female_members", "ethnic_members")


def upgrade() -> None:
    op.add_column("households", sa.Column("census_form_number", sa.String(20), nullable=True))
    op.create_unique_constraint(
        "uq_households_census_form_number", "households", ["census_form_number"]
    )
    op.add_column("households", sa.Column("tenure", sa.String(16), nullable=True))
    op.add_column("households", sa.Column("housing_status", sa.String(16), nullable=True))
    for col in COUNTS:
        op.add_column(
            "households", sa.Column(col, sa.SmallInteger(), nullable=False, server_default=ZERO)
        )
    op.add_column(
        "households",
        sa.Column("losses", postgresql.ARRAY(sa.String(24)), nullable=False, server_default=EMPTY),
    )

    op.add_column("aid_deliveries", sa.Column("act_number", sa.String(20), nullable=True))
    op.create_unique_constraint("uq_aid_deliveries_act_number", "aid_deliveries", ["act_number"])
    op.add_column("aid_deliveries", sa.Column("delivered_by", sa.String(80), nullable=True))
    op.add_column(
        "aid_deliveries",
        sa.Column("quantity", sa.SmallInteger(), nullable=False, server_default=sa.text("1")),
    )
    op.add_column("aid_deliveries", sa.Column("amount_cop", sa.Numeric(14, 2), nullable=True))
    op.add_column("aid_deliveries", sa.Column("months", sa.SmallInteger(), nullable=True))
    op.add_column(
        "aid_deliveries",
        sa.Column("shelter_id", sa.UUID(), sa.ForeignKey("shelters.id"), nullable=True),
    )
    op.add_column(
        "aid_deliveries",
        sa.Column("signed", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column(
        "aid_deliveries", sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True)
    )

    op.add_column("shelters", sa.Column("operator", sa.String(120), nullable=True))
    op.add_column(
        "shelters",
        sa.Column("status", sa.String(12), nullable=False, server_default=sa.text("'abierto'")),
    )
    op.add_column(
        "shelters",
        sa.Column(
            "services", postgresql.ARRAY(sa.String(24)), nullable=False, server_default=EMPTY
        ),
    )


def downgrade() -> None:
    for col in ("services", "status", "operator"):
        op.drop_column("shelters", col)
    for col in ("ended_at", "signed", "shelter_id", "months", "amount_cop", "quantity"):
        op.drop_column("aid_deliveries", col)
    op.drop_column("aid_deliveries", "delivered_by")
    op.drop_constraint("uq_aid_deliveries_act_number", "aid_deliveries", type_="unique")
    op.drop_column("aid_deliveries", "act_number")
    for col in ("losses", *COUNTS, "housing_status", "tenure"):
        op.drop_column("households", col)
    op.drop_constraint("uq_households_census_form_number", "households", type_="unique")
    op.drop_column("households", "census_form_number")
