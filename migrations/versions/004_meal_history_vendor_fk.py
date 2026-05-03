"""Link cook.meal_history to mercian.vendors.

Adds a nullable vendor_id FK so meal entries can record which takeaway
or restaurant they came from. NULL for home-cooked meals; populated for
takeaways and meals out (where Mercian holds the vendor).

Revision ID: 004
Revises: 003
Create Date: 2026-05-03
"""

from alembic import op

revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE cook.meal_history
        ADD COLUMN IF NOT EXISTS vendor_id UUID
        REFERENCES mercian.vendors(id) ON DELETE SET NULL
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_cook_meal_history_vendor "
        "ON cook.meal_history(vendor_id) WHERE vendor_id IS NOT NULL"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS cook.ix_cook_meal_history_vendor")
    op.execute("ALTER TABLE cook.meal_history DROP COLUMN IF EXISTS vendor_id")
