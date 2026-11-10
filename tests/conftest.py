import os
import sys
from pathlib import Path

# Ensure monorepo packages and services are in python path
root_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root_dir))
sys.path.insert(0, str(root_dir / "packages" / "contracts"))
sys.path.insert(0, str(root_dir / "packages" / "db"))
sys.path.insert(0, str(root_dir / "services" / "api"))
sys.path.insert(0, str(root_dir / "services" / "orchestrator"))

os.environ["ENVIRONMENT"] = "testing"
os.environ["LANGGRAPH_CHECKPOINT_SAVER"] = "memory"
if "DATABASE_URL" not in os.environ:
    os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
if "DATABASE_URL_SYNC" not in os.environ:
    os.environ["DATABASE_URL_SYNC"] = "sqlite:///:memory:"

