"""Tests for tool/semantic-model/inspect.py."""

from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import MagicMock

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
INSPECT_PATH = ROOT / "tool" / "semantic-model" / "inspect.py"


def load_inspect() -> ModuleType:
    spec = importlib.util.spec_from_file_location("semantic_model_inspect", INSPECT_PATH)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ── sample DataFrames ─────────────────────────────────────────────────────────

def _datasets_df() -> pd.DataFrame:
    return pd.DataFrame([
        {"Dataset Id": "aaa-111", "Dataset Name": "Sales Model",    "Description": "Core KPIs"},
        {"Dataset Id": "bbb-222", "Dataset Name": "Inventory Model", "Description": ""},
    ])


def _tables_df() -> pd.DataFrame:
    return pd.DataFrame([
        {"Name": "Sales",    "Hidden": False},
        {"Name": "Date",     "Hidden": False},
        {"Name": "Customer", "Hidden": True},
    ])


def _columns_df() -> pd.DataFrame:
    return pd.DataFrame([
        {"Table Name": "Sales",    "Column Name": "OrderID",    "Data Type": "Int64",   "Hidden": False, "Column Type": "Regular",    "Expression": ""},
        {"Table Name": "Sales",    "Column Name": "Amount",     "Data Type": "Decimal", "Hidden": False, "Column Type": "Regular",    "Expression": ""},
        {"Table Name": "Sales",    "Column Name": "RowNumber",  "Data Type": "Int64",   "Hidden": True,  "Column Type": "RowNumber",  "Expression": ""},
        {"Table Name": "Date",     "Column Name": "Date",       "Data Type": "DateTime","Hidden": False, "Column Type": "Regular",    "Expression": ""},
        {"Table Name": "Date",     "Column Name": "MonthName",  "Data Type": "String",  "Hidden": False, "Column Type": "Calculated", "Expression": 'FORMAT([Date], "MMMM")'},
        {"Table Name": "Customer", "Column Name": "CustomerKey","Data Type": "Int64",   "Hidden": False, "Column Type": "Regular",    "Expression": ""},
    ])


def _measures_df() -> pd.DataFrame:
    return pd.DataFrame([
        {"Table Name": "Sales", "Measure Name": "Total Revenue", "Measure Expression": "SUM(Sales[Amount])", "Measure Format String": "#,##0.00", "Measure Description": "Gross before returns"},
        {"Table Name": "Sales", "Measure Name": "Net Revenue",   "Measure Expression": "[Total Revenue] - [Returns]", "Measure Format String": "", "Measure Description": ""},
    ])


def _relationships_df() -> pd.DataFrame:
    return pd.DataFrame([
        {"From Table": "Sales", "From Column": "CustomerKey", "To Table": "Customer", "To Column": "CustomerKey", "Is Active": True,  "Cross Filtering Behavior": "BothDirections"},
        {"From Table": "Sales", "From Column": "DateKey",     "To Table": "Date",     "To Column": "DateKey",     "Is Active": False, "Cross Filtering Behavior": ""},
    ])


def _mock_fabric() -> MagicMock:
    fabric = MagicMock()
    fabric.list_datasets.return_value     = _datasets_df()
    fabric.list_tables.return_value       = _tables_df()
    fabric.list_columns.return_value      = _columns_df()
    fabric.list_measures.return_value     = _measures_df()
    fabric.list_relationships.return_value = _relationships_df()
    return fabric


# ── helper: inject mock sempy into sys.modules ────────────────────────────────

def _inject_sempy(fabric_mock: MagicMock) -> None:
    sempy_mod  = ModuleType("sempy")
    fabric_mod = ModuleType("sempy.fabric")
    for attr in dir(fabric_mock):
        if not attr.startswith("_"):
            setattr(fabric_mod, attr, getattr(fabric_mock, attr))
    sempy_mod.fabric = fabric_mod
    sys.modules.setdefault("sempy",        sempy_mod)
    sys.modules["sempy.fabric"] = fabric_mod


# ── _setup_azure_auth ─────────────────────────────────────────────────────────

def test_setup_azure_auth_maps_fabric_vars(monkeypatch):
    mod = load_inspect()
    monkeypatch.setenv("FABRIC_TENANT_ID",     "tenant-x")
    monkeypatch.setenv("FABRIC_CLIENT_ID",     "client-x")
    monkeypatch.setenv("FABRIC_CLIENT_SECRET", "secret-x")
    monkeypatch.delenv("AZURE_TENANT_ID",     raising=False)
    monkeypatch.delenv("AZURE_CLIENT_ID",     raising=False)
    monkeypatch.delenv("AZURE_CLIENT_SECRET", raising=False)

    mod._setup_azure_auth()

    # Non-sensitive IDs are mapped to AZURE_* so DefaultAzureCredential can find them.
    assert os.environ["AZURE_TENANT_ID"] == "tenant-x"
    assert os.environ["AZURE_CLIENT_ID"] == "client-x"
    # The client secret must NOT be propagated into the environment (S15).
    assert "AZURE_CLIENT_SECRET" not in os.environ


def test_setup_azure_auth_does_not_overwrite_existing(monkeypatch):
    mod = load_inspect()
    monkeypatch.setenv("FABRIC_TENANT_ID", "fabric-tenant")
    monkeypatch.setenv("AZURE_TENANT_ID",  "existing-tenant")

    mod._setup_azure_auth()

    assert os.environ["AZURE_TENANT_ID"] == "existing-tenant"


# ── _require_sempy ────────────────────────────────────────────────────────────

def test_require_sempy_raises_on_missing(monkeypatch):
    mod = load_inspect()
    monkeypatch.delitem(sys.modules, "sempy",        raising=False)
    monkeypatch.delitem(sys.modules, "sempy.fabric", raising=False)

    with pytest.raises(SystemExit, match="semantic-link"):
        mod._require_sempy()


def test_require_sempy_returns_module_when_present():
    mod = load_inspect()
    fabric_mock = _mock_fabric()
    _inject_sempy(fabric_mock)

    result = mod._require_sempy()
    assert result is not None


# ── _resolve_model ────────────────────────────────────────────────────────────

def test_resolve_model_by_name():
    mod = load_inspect()
    df = _datasets_df()
    name, mid = mod._resolve_model(df, "Sales Model")
    assert name == "Sales Model"
    assert mid  == "aaa-111"


def test_resolve_model_by_id():
    mod = load_inspect()
    df = _datasets_df()
    name, mid = mod._resolve_model(df, "bbb-222")
    assert name == "Inventory Model"
    assert mid  == "bbb-222"


def test_resolve_model_case_insensitive():
    mod = load_inspect()
    df = _datasets_df()
    name, _ = mod._resolve_model(df, "sales model")
    assert name == "Sales Model"


def test_resolve_model_not_found_exits():
    mod = load_inspect()
    df = _datasets_df()
    with pytest.raises(SystemExit, match="No semantic model"):
        mod._resolve_model(df, "nonexistent")


def test_resolve_model_ambiguous_exits():
    mod = load_inspect()
    df = pd.DataFrame([
        {"Dataset Id": "x-1", "Dataset Name": "Dup Model", "Description": ""},
        {"Dataset Id": "x-2", "Dataset Name": "Dup Model", "Description": ""},
    ])
    with pytest.raises(SystemExit, match="Multiple models"):
        mod._resolve_model(df, "Dup Model")


# ── _print_list ───────────────────────────────────────────────────────────────

def test_print_list_shows_all_models(capsys):
    mod = load_inspect()
    mod._print_list(_datasets_df())
    out = capsys.readouterr().out
    assert "Sales Model"    in out
    assert "aaa-111"        in out
    assert "Core KPIs"      in out
    assert "Inventory Model" in out


def test_print_list_empty_df(capsys):
    mod = load_inspect()
    mod._print_list(pd.DataFrame())
    assert "No semantic models" in capsys.readouterr().out


# ── _print_model ──────────────────────────────────────────────────────────────

def test_print_model_shows_tables_columns_measures_relationships(capsys):
    mod = load_inspect()
    detail = {
        "tables":        _tables_df(),
        "columns":       _columns_df(),
        "measures":      _measures_df(),
        "relationships": _relationships_df(),
    }
    # S16: include_hidden=True and include_expressions=True to verify full output
    mod._print_model("Sales Model", "aaa-111", detail, include_hidden=True, include_expressions=True)
    out = capsys.readouterr().out

    assert "Sales Model"    in out
    assert "aaa-111"        in out
    # tables
    assert "Sales"          in out
    assert "Date"           in out
    assert "Customer"       in out
    assert "[hidden]"       in out
    # columns
    assert "OrderID"        in out
    assert "MonthName"      in out
    assert "[calc]"         in out
    assert "RowNumber"  not in out        # RowNumber columns must be suppressed
    # measures
    assert "Total Revenue"  in out
    assert "SUM(Sales[Amount])" in out
    assert "#,##0.00"       in out
    assert "Gross before returns" in out
    # relationships
    assert "CustomerKey"    in out
    assert "BothDirections" in out
    assert "[inactive]"     in out        # DateKey rel is inactive


# ── main (integration) ────────────────────────────────────────────────────────

def test_main_list_command(capsys, monkeypatch, tmp_path):
    mod = load_inspect()
    fabric_mock = _mock_fabric()
    _inject_sempy(fabric_mock)

    env_file = tmp_path / ".env"
    env_file.write_text("FABRIC_WORKSPACE_ID=ws-test-id\n")
    monkeypatch.setattr(mod, "SCRIPT_ROOT", tmp_path)
    monkeypatch.setattr(mod, "_require_sempy", lambda: fabric_mock)

    assert mod.main(["list"]) == 0
    out = capsys.readouterr().out
    assert "Sales Model"    in out
    assert "Inventory Model" in out


def test_main_show_command(capsys, monkeypatch, tmp_path):
    mod = load_inspect()
    fabric_mock = _mock_fabric()

    env_file = tmp_path / ".env"
    env_file.write_text("FABRIC_WORKSPACE_ID=ws-test-id\n")
    monkeypatch.setattr(mod, "SCRIPT_ROOT", tmp_path)
    monkeypatch.setattr(mod, "_require_sempy", lambda: fabric_mock)

    assert mod.main(["show", "Sales Model"]) == 0
    out = capsys.readouterr().out
    assert "Sales Model"    in out
    assert "Total Revenue"  in out
    assert "CustomerKey"    in out


def test_main_show_json(capsys, monkeypatch, tmp_path):
    import json
    mod = load_inspect()
    fabric_mock = _mock_fabric()

    env_file = tmp_path / ".env"
    env_file.write_text("FABRIC_WORKSPACE_ID=ws-test-id\n")
    monkeypatch.setattr(mod, "SCRIPT_ROOT", tmp_path)
    monkeypatch.setattr(mod, "_require_sempy", lambda: fabric_mock)

    assert mod.main(["show", "Sales Model", "--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["model"]["name"] == "Sales Model"
    assert isinstance(data["tables"],  list)
    assert isinstance(data["measures"], list)
    assert any(m["Measure Name"] == "Total Revenue" for m in data["measures"])


def test_main_missing_workspace_exits(monkeypatch, tmp_path):
    mod = load_inspect()
    monkeypatch.setattr(mod, "SCRIPT_ROOT", tmp_path)
    monkeypatch.delenv("FABRIC_WORKSPACE_ID", raising=False)

    with pytest.raises(SystemExit, match="FABRIC_WORKSPACE_ID"):
        mod.main(["list"])
