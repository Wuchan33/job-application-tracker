"""merge email types

Revision ID: 75f095e860c1
Revises: 47fefddacbb1
Create Date: 2026-11-22 23:38:47.155139

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '75f095e860c1'
down_revision: Union[str, Sequence[str], None] = '47fefddacbb1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

CONSTRAINT_NAME = "emailtype"
COLUMNS = [("application", "status"), ("email", "type")]

OLD_TYPES = [
    "applied",
    "online_test",
    "hr_interview",
    "technical_interview",
    "take_home",
    "final_interview",
    "offer",
    "rejection",
    "other",
]
NEW_TYPES = [
    "applied",
    "online_assessment",
    "hr_interview",
    "interview",
    "offer",
    "rejection",
    "other",
]

UPGRADE_MAPPING = {
    "online_test": "online_assessment",
    "take_home": "online_assessment",
    "technical_interview": "interview",
    "final_interview": "interview",
}
DOWNGRADE_MAPPING = {
    "online_assessment": "online_test",
    "interview": "technical_interview",
}


def _check(column: str, types: list[str]) -> str:
    values = ", ".join(f"'{t}'" for t in types)
    return f"{column} IN ({values})"


def _migrate(types: list[str], mapping: dict[str, str]) -> None:
    for table, column in COLUMNS:
        op.drop_constraint(CONSTRAINT_NAME, table, type_="check")
        for old, new in mapping.items():
            op.execute(f"UPDATE {table} SET {column} = '{new}' WHERE {column} = '{old}'")
        op.create_check_constraint(CONSTRAINT_NAME, table, _check(column, types))


def upgrade() -> None:
    """Upgrade schema."""
    _migrate(NEW_TYPES, UPGRADE_MAPPING)


def downgrade() -> None:
    """Downgrade schema."""
    _migrate(OLD_TYPES, DOWNGRADE_MAPPING)
