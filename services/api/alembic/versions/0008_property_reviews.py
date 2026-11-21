"""property reviews

Revisión a predio según el formato oficial GUE-RPD-FR-02 v4 de la Alcaldía de Manizales: liga la
evaluación de habitabilidad con el hogar del censo y registra evento, afectación, derivaciones a
entidades y recomendación de evacuación. Sin datos personales en claro (Ley 1581).

Revision ID: 0008
Revises: 0007
Create Date: 2026-11-21 16:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0008"
down_revision: str | Sequence[str] | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "property_reviews",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("source", sa.String(64), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("form_number", sa.String(20), nullable=True, unique=True),
        sa.Column(
            "inspection_id",
            sa.UUID(),
            sa.ForeignKey("building_inspections.id"),
            nullable=False,
            unique=True,
        ),
        sa.Column("property_id", sa.String(160), nullable=False),
        sa.Column("household_id", sa.UUID(), sa.ForeignKey("households.id"), nullable=True),
        sa.Column("respondent_relation", sa.String(20), nullable=True),
        sa.Column("owner_hash", sa.String(64), nullable=True),
        sa.Column("residents", sa.SmallInteger(), nullable=False),
        sa.Column("event_status", sa.String(16), nullable=False),
        sa.Column("event_types", postgresql.ARRAY(sa.String(24)), nullable=False),
        sa.Column("event_other", sa.Text(), nullable=True),
        sa.Column("structural_causes", postgresql.ARRAY(sa.String(32)), nullable=False),
        sa.Column("affectation", sa.String(16), nullable=False),
        sa.Column("affected_areas_m2", postgresql.JSONB(), nullable=False),
        sa.Column("belongings_loss", sa.Text(), nullable=True),
        sa.Column("referrals", postgresql.ARRAY(sa.String(32)), nullable=False),
        sa.Column("referral_other", sa.Text(), nullable=True),
        sa.Column("referrals_done", postgresql.ARRAY(sa.String(32)), nullable=False),
        sa.Column("evacuation_recommended", sa.Boolean(), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reviewer_agency", sa.String(80), nullable=False),
        sa.Column("notified_signed", sa.Boolean(), nullable=False),
        sa.Column("recorded_by_role", sa.String(32), nullable=False),
        sa.CheckConstraint("residents >= 0", name="ck_property_review_residents"),
    )
    op.create_index(
        "ix_property_reviews_property", "property_reviews", ["property_id", "reviewed_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_property_reviews_property", table_name="property_reviews")
    op.drop_table("property_reviews")
