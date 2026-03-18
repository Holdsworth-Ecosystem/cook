"""Add ON DELETE CASCADE to recipe_ratings.meal_id foreign key.

Revision ID: 003
Revises: 002
Create Date: 2026-03-18

DAT-001: The FK from recipe_ratings.meal_id to meal_history.id was created
without ON DELETE CASCADE, meaning deleting a meal_history row would fail
if any ratings referenced it.  Drop and re-create the constraint.
"""

from alembic import op

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Find and drop the existing FK constraint on recipe_ratings.meal_id
    op.execute("""
        ALTER TABLE cook.recipe_ratings
        DROP CONSTRAINT IF EXISTS recipe_ratings_meal_id_fkey
    """)

    # Re-create with ON DELETE CASCADE
    op.execute("""
        ALTER TABLE cook.recipe_ratings
        ADD CONSTRAINT recipe_ratings_meal_id_fkey
        FOREIGN KEY (meal_id) REFERENCES cook.meal_history(id)
        ON DELETE CASCADE
    """)


def downgrade() -> None:
    op.execute("""
        ALTER TABLE cook.recipe_ratings
        DROP CONSTRAINT IF EXISTS recipe_ratings_meal_id_fkey
    """)

    op.execute("""
        ALTER TABLE cook.recipe_ratings
        ADD CONSTRAINT recipe_ratings_meal_id_fkey
        FOREIGN KEY (meal_id) REFERENCES cook.meal_history(id)
    """)
