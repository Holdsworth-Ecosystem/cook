"""Create cook schema and tables.

Revision ID: 001
Create Date: 2026-03-06
"""

from alembic import op

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # dietary_profiles
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS cook.dietary_profiles (
            id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            member_id   UUID NOT NULL REFERENCES sturmey.household_members(id) ON DELETE CASCADE,
            item        TEXT NOT NULL,
            item_type   TEXT NOT NULL DEFAULT 'ingredient',
            severity    TEXT NOT NULL,
            reason      TEXT,
            notes       TEXT,
            source      TEXT NOT NULL DEFAULT 'manual',
            created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE (member_id, item, item_type)
        )
        """
    )

    # meal_history
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS cook.meal_history (
            id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            recipe_id   UUID,
            recipe_name TEXT NOT NULL,
            served_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            diners      UUID[] NOT NULL,
            notes       TEXT,
            created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )

    # recipe_ratings
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS cook.recipe_ratings (
            id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            recipe_id   UUID,
            meal_id     UUID REFERENCES cook.meal_history(id),
            member_id   UUID NOT NULL REFERENCES sturmey.household_members(id) ON DELETE CASCADE,
            rating      INTEGER NOT NULL CHECK (rating BETWEEN 1 AND 5),
            comment     TEXT,
            created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE (meal_id, member_id)
        )
        """
    )

    # Indexes
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_cook_dietary_profiles_member
        ON cook.dietary_profiles (member_id)
        """
    )

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_cook_meal_history_served
        ON cook.meal_history (served_at DESC)
        """
    )

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_cook_recipe_ratings_recipe
        ON cook.recipe_ratings (recipe_id)
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS cook.recipe_ratings")
    op.execute("DROP TABLE IF EXISTS cook.meal_history")
    op.execute("DROP TABLE IF EXISTS cook.dietary_profiles")
