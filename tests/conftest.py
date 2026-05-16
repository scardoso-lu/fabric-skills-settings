"""Add tool/ subdirectories to sys.path so test modules can import build and manage."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tool" / "notebook"))
sys.path.insert(0, str(ROOT / "tool" / "pipeline"))
