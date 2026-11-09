import importlib.util
from pathlib import Path


def test_alembic_initial_migration_syntax_and_structure():
    migration_path = Path("packages/db/migrations/versions/001_initial_schema.py")
    assert migration_path.exists(), "Migration script 001_initial_schema.py does not exist."

    # Dynamically import the migration module
    spec = importlib.util.spec_from_file_location("migration_001", migration_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    assert hasattr(module, "upgrade"), "Migration script must have an upgrade() function."
    assert hasattr(module, "downgrade"), "Migration script must have a downgrade() function."
    assert module.revision == "001_initial_schema"
    assert module.down_revision is None

