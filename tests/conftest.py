"""Add tool/ and packaging/builders/ to sys.path so tests can import runtime + build-time modules."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tool" / "notebook"))
sys.path.insert(0, str(ROOT / "tool" / "pipeline"))
sys.path.insert(0, str(ROOT / "tool"))
sys.path.insert(0, str(ROOT / "packaging" / "builders"))
