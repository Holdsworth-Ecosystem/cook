"""Add recipe_overrides table for per-member per-recipe manual suitability flags.

Revision ID: 002
Create Date: 2026-03-08

When the household flags a recipe as unsuitable (e.g. "the koftas have roti,
that's wheat") the LLM should only need to think about it once. The override
is stored here and Cook's scorer reads it on every future suggestion, so the
same mistake never repeats.
"""

from alembic import op

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS cook.recipe_overrides (
            id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            member_id       UUID NOT NULL REFERENCES sturmey.household_members(id) ON DELETE CASCADE,
            recipe_id       UUID NOT NULL REFERENCES holdsworth.recipes(id) ON DELETE CASCADE,
            suitability     TEXT NOT NULL,
            reason          TEXT,
            substitution    TEXT,
            source          TEXT NOT NULL DEFAULT 'conversation',
            created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE (member_id, recipe_id)
        )
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_cook_recipe_overrides_member
        ON cook.recipe_overrides (member_id)
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_cook_recipe_overrides_recipe
        ON cook.recipe_overrides (recipe_id)
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS cook.recipe_overrides")
