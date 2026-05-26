"""sys.path setup for tests.

Repo root first so `from server.tools.X import tools as X_tools` works.
Plus the cli/tools/<area>/ dirs because their build.py / manage.py modules
are loaded via importlib from a few test files. cli/tools/ as a whole so
`from lint import LINTS` resolves to the relocated lint package.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
# tests/ on path so `from _validation.X import collect_errors` resolves.
sys.path.insert(0, str(ROOT / "tests"))
sys.path.insert(0, str(ROOT / "cli" / "tools"))
sys.path.insert(0, str(ROOT / "cli" / "tools" / "notebook"))
sys.path.insert(0, str(ROOT / "cli" / "tools" / "pipeline"))
sys.path.insert(0, str(ROOT / "server" / "tools"))
sys.path.insert(0, str(ROOT / "server"))
sys.path.insert(0, str(ROOT / "server" / "builders"))
