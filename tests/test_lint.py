"""Smoke tests for the tool/lint/ scaffold.

These tests build a synthetic mini-target with one offending file per rule
and assert that:
  - the registered lints find them,
  - emit_report returns exit-code 1,
  - a clean target produces zero findings + exit-code 0.

The tests do NOT depend on the live repository state — every fixture is
written into ``tmp_path``.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "cli" / "tools"))

from lint import LINTS  # noqa: E402
from lint.core import run_all  # noqa: E402


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_clean_target_passes(tmp_path: Path) -> None:
    _write(
        tmp_path / "workspace" / "demo" / "bronze_demo.py",
        '# %% [contract]\nimport os\nuser = os.environ["DEMO_USER"]\n',
    )
    findings, code = run_all(LINTS, tmp_path)
    assert findings == []
    assert code == 0


# ── SEC-01: hardcoded secrets ────────────────────────────────────────────────

def test_sec_01_flags_jwt_literal(tmp_path: Path) -> None:
    _write(
        tmp_path / "workspace" / "demo" / "bronze_demo.py",
        "token = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.AAAAAAAAAA.BBBBBBBBBB'\n",
    )
    findings, code = run_all(LINTS, tmp_path)
    assert code == 1
    assert any(f.rule_id == "SEC-01" and "JWT" in f.msg for f in findings)


def test_sec_01_flags_account_key(tmp_path: Path) -> None:
    _write(
        tmp_path / "workspace" / "demo" / "bronze_demo.py",
        "cs = 'AccountKey=AAAABBBBCCCCDDDDEEEEFFFFGGGGHHHHIIIIJJJJKKKK=='\n",
    )
    findings, code = run_all(LINTS, tmp_path)
    assert code == 1
    assert any(f.rule_id == "SEC-01" and "AccountKey" in f.msg for f in findings)


def test_sec_01_flags_password_assignment(tmp_path: Path) -> None:
    _write(
        tmp_path / "workspace" / "demo" / "bronze_demo.py",
        'password = "hunter2-not-a-placeholder"\n',
    )
    findings, code = run_all(LINTS, tmp_path)
    assert code == 1
    assert any(f.rule_id == "SEC-01" for f in findings)


def test_sec_01_allows_os_environ_lookup(tmp_path: Path) -> None:
    _write(
        tmp_path / "workspace" / "demo" / "bronze_demo.py",
        'import os\npassword = os.environ["SRC_ORDERS_PASS"]\n',
    )
    findings, code = run_all(LINTS, tmp_path)
    assert [f for f in findings if f.rule_id == "SEC-01"] == []
    assert code == 0


def test_sec_01_allows_env_example_placeholder(tmp_path: Path) -> None:
    _write(
        tmp_path / "workspace" / "demo" / "bronze_demo.py",
        'password = "<your-key-here>"  # REPLACE_ME via .env.example\n',
    )
    findings, code = run_all(LINTS, tmp_path)
    assert [f for f in findings if f.rule_id == "SEC-01"] == []
    assert code == 0


# ── DE-09: Faker must be seeded ──────────────────────────────────────────────

def test_de_09_flags_faker_without_seed(tmp_path: Path) -> None:
    _write(
        tmp_path / "tool" / "data" / "mock.py",
        "from faker import Faker\nfake = Faker()\nname = fake.name()\n",
    )
    findings, code = run_all(LINTS, tmp_path)
    assert code == 1
    matches = [f for f in findings if f.rule_id == "DE-09"]
    assert len(matches) == 1
    assert matches[0].line == 1


def test_de_09_accepts_class_level_seed(tmp_path: Path) -> None:
    _write(
        tmp_path / "tool" / "data" / "mock.py",
        "from faker import Faker\nFaker.seed(42)\nfake = Faker()\n",
    )
    findings, code = run_all(LINTS, tmp_path)
    assert [f for f in findings if f.rule_id == "DE-09"] == []
    assert code == 0


def test_de_09_accepts_instance_level_seed(tmp_path: Path) -> None:
    _write(
        tmp_path / "tool" / "data" / "mock.py",
        "from faker import Faker\nfake = Faker()\nfake.seed_instance(42)\n",
    )
    findings, code = run_all(LINTS, tmp_path)
    assert [f for f in findings if f.rule_id == "DE-09"] == []
    assert code == 0


def test_de_09_accepts_mimesis_with_seed(tmp_path: Path) -> None:
    _write(
        tmp_path / "tool" / "data" / "mock.py",
        "from mimesis import Generic\ng = Generic()\ng.random.seed(42)\n",
    )
    findings, code = run_all(LINTS, tmp_path)
    assert [f for f in findings if f.rule_id == "DE-09"] == []
    assert code == 0


def test_de_09_ignores_modules_without_faker(tmp_path: Path) -> None:
    _write(
        tmp_path / "tool" / "data" / "no_faker.py",
        "import os\nimport json\n",
    )
    findings, code = run_all(LINTS, tmp_path)
    assert [f for f in findings if f.rule_id == "DE-09"] == []
    assert code == 0
