from sqlalchemy import create_engine

from packages.db.base import Base


def test_all_twenty_models_registered_in_metadata():
    """Verify that all 20 required domain and authoritative tables are present in Base.metadata."""
    table_names = set(Base.metadata.tables.keys())
    expected_tables = {
        "users",
        "candidate_profiles",
        "profile_evidence",
        "preferences",
        "job_sources",
        "job_listings",
        "job_matches",
        "saved_jobs",
        "application_packages",
        "applications",
        "application_events",
        "email_drafts",
        "research_sources",
        "interview_plans",
        "mock_interviews",
        "agent_runs",
        "workflow_checkpoints",
        "approvals",
        "audit_events",
        "model_usage",
    }
    missing = expected_tables - table_names
    assert not missing, f"Missing tables in metadata: {missing}"


def test_in_memory_sqlite_schema_creation():
    """Verify that all tables, foreign keys, and indexes can be created in an engine cleanly."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    # Inspect created tables
    from sqlalchemy import inspect
    inspector = inspect(engine)
    created_tables = set(inspector.get_table_names())
    assert "users" in created_tables
    assert "candidate_profiles" in created_tables
    assert "profile_evidence" in created_tables
    assert "job_listings" in created_tables
    assert "workflow_checkpoints" in created_tables
    assert "approvals" in created_tables
    assert "audit_events" in created_tables

