"""Regression tests for tool/notebook/build.py.

Covers pure functions that can be exercised without a live Fabric workspace.
Tests that require env-var resolution use monkeypatch to avoid coupling to
any local .env file present in the repo root.
"""
import json

import pytest

import build


# ---------------------------------------------------------------------------
# _env_name — display name → env-var suffix
# ---------------------------------------------------------------------------

class TestEnvName:
    def test_already_uppercase(self):
        assert build._env_name("DATALAKE") == "DATALAKE"

    def test_spaces_become_underscores(self):
        assert build._env_name("Data Lake") == "DATA_LAKE"

    def test_hyphens_become_underscores(self):
        assert build._env_name("my-lakehouse") == "MY_LAKEHOUSE"

    def test_mixed_spaces_and_hyphens(self):
        assert build._env_name("bronze-silver lake") == "BRONZE_SILVER_LAKE"

    def test_lowercase_uppercase(self):
        assert build._env_name("datalake") == "DATALAKE"


# ---------------------------------------------------------------------------
# _parse_sentinels — kernel + lakehouse + warehouse detection
# ---------------------------------------------------------------------------

class TestParseSentinels:
    def test_no_sentinels(self):
        python_kernel, lakehouses, warehouses = build._parse_sentinels("x = 1\n")
        assert python_kernel is False
        assert lakehouses == []
        assert warehouses == []

    def test_python_kernel_first_line(self):
        source = "# FABRIC_KERNEL: python\nx = 1\n"
        python_kernel, _, _ = build._parse_sentinels(source)
        assert python_kernel is True

    def test_python_kernel_not_first_line_ignored(self):
        source = "x = 1\n# FABRIC_KERNEL: python\n"
        python_kernel, _, _ = build._parse_sentinels(source)
        assert python_kernel is False

    def test_python_kernel_after_leading_whitespace(self):
        # lstrip() before startswith check
        source = "  # FABRIC_KERNEL: python\nx = 1\n"
        python_kernel, _, _ = build._parse_sentinels(source)
        assert python_kernel is True

    def test_single_lakehouse(self):
        source = "# FABRIC_LAKEHOUSE: DATALAKE\n"
        _, lakehouses, warehouses = build._parse_sentinels(source)
        assert lakehouses == ["DATALAKE"]
        assert warehouses == []

    def test_multiple_lakehouses_ordered(self):
        source = "# FABRIC_LAKEHOUSE: BRONZE\n# FABRIC_LAKEHOUSE: SILVER\n"
        _, lakehouses, _ = build._parse_sentinels(source)
        assert lakehouses == ["BRONZE", "SILVER"]

    def test_warehouse(self):
        source = "# FABRIC_WAREHOUSE: DATA_WAREHOUSE\n"
        _, lakehouses, warehouses = build._parse_sentinels(source)
        assert lakehouses == []
        assert warehouses == ["DATA_WAREHOUSE"]

    def test_all_sentinels(self):
        source = (
            "# FABRIC_KERNEL: python\n"
            "# FABRIC_LAKEHOUSE: DATALAKE\n"
            "# FABRIC_LAKEHOUSE: BRONZE\n"
            "# FABRIC_WAREHOUSE: DATA_WAREHOUSE\n"
        )
        python_kernel, lakehouses, warehouses = build._parse_sentinels(source)
        assert python_kernel is True
        assert lakehouses == ["DATALAKE", "BRONZE"]
        assert warehouses == ["DATA_WAREHOUSE"]

    def test_sentinel_names_stripped(self):
        source = "# FABRIC_LAKEHOUSE:   DATALAKE  \n"
        _, lakehouses, _ = build._parse_sentinels(source)
        assert lakehouses == ["DATALAKE"]


# ---------------------------------------------------------------------------
# split_cells — # %% splitting and [parameters] detection
# ---------------------------------------------------------------------------

class TestSplitCells:
    def test_single_regular_cell(self):
        cells = build.split_cells("# %%\nx = 1\n")
        assert len(cells) == 1
        is_params, content = cells[0]
        assert is_params is False
        assert "x = 1" in content

    def test_two_regular_cells(self):
        cells = build.split_cells("# %%\nx = 1\n# %%\ny = 2\n")
        assert len(cells) == 2
        assert all(not is_p for is_p, _ in cells)
        assert "x = 1" in cells[0][1]
        assert "y = 2" in cells[1][1]

    def test_parameters_cell_detected(self):
        cells = build.split_cells("# %% [parameters]\nWH = ''\n# %%\nx = 1\n")
        assert len(cells) == 2
        assert cells[0][0] is True
        assert cells[1][0] is False

    def test_parameters_cell_with_spaces_in_marker(self):
        cells = build.split_cells("# %%  [parameters]\nWH = ''\n")
        assert len(cells) == 1
        assert cells[0][0] is True

    def test_empty_cell_filtered_out(self):
        cells = build.split_cells("# %%\n\n# %%\ny = 2\n")
        assert len(cells) == 1
        assert "y = 2" in cells[0][1]

    def test_content_before_first_marker_ignored(self):
        cells = build.split_cells("# file header\n# %%\nx = 1\n")
        assert len(cells) == 1

    def test_cell_content_stripped(self):
        cells = build.split_cells("# %%\n\n  x = 1  \n\n")
        assert cells[0][1] == "x = 1"

    def test_returns_list_of_tuples(self):
        cells = build.split_cells("# %%\nx = 1\n")
        assert isinstance(cells, list)
        assert isinstance(cells[0], tuple)
        assert len(cells[0]) == 2


# ---------------------------------------------------------------------------
# _meta_block — dict → # META comment block
# ---------------------------------------------------------------------------

class TestMetaBlock:
    def test_starts_with_metadata_header(self):
        block = build._meta_block({"a": 1})
        assert block.startswith("# METADATA ********************\n\n")

    def test_all_content_lines_prefixed(self):
        block = build._meta_block({"language": "python", "language_group": "jupyter_python"})
        for line in block.splitlines():
            if line.strip():
                assert line.startswith("# META") or line.startswith("# METADATA"), repr(line)

    def test_json_content_is_valid(self):
        block = build._meta_block({"language": "python"})
        json_lines = [
            line[len("# META "):] for line in block.splitlines()
            if line.startswith("# META ") and not line.startswith("# METADATA")
        ]
        parsed = json.loads("\n".join(json_lines))
        assert parsed == {"language": "python"}

    def test_nested_dict_serialised(self):
        content = {"kernel_info": {"name": "synapse_pyspark"}}
        block = build._meta_block(content)
        assert '"kernel_info"' in block
        assert '"synapse_pyspark"' in block


# ---------------------------------------------------------------------------
# _cell_meta — per-cell language metadata
# ---------------------------------------------------------------------------

class TestCellMeta:
    def test_python_kernel_language_group(self):
        block = build._cell_meta(python_kernel=True)
        assert '"language_group": "jupyter_python"' in block

    def test_python_kernel_language(self):
        block = build._cell_meta(python_kernel=True)
        assert '"language": "python"' in block

    def test_pyspark_kernel_language_group(self):
        block = build._cell_meta(python_kernel=False)
        assert '"language_group": "synapse_pyspark"' in block

    def test_pyspark_kernel_language(self):
        block = build._cell_meta(python_kernel=False)
        assert '"language": "python"' in block


# ---------------------------------------------------------------------------
# _notebook_meta — notebook-level kernel + dependency metadata
# ---------------------------------------------------------------------------

def _parse_meta_json(block: str) -> dict:
    """Extract the JSON payload from a _meta_block string."""
    json_lines = [
        line[len("# META "):] for line in block.splitlines()
        if line.startswith("# META ") and not line.startswith("# METADATA")
    ]
    return json.loads("\n".join(json_lines))


class TestNotebookMeta:
    def test_pyspark_no_deps_returns_empty(self):
        result = build._notebook_meta(python_kernel=False, lakehouses=[], warehouses=[])
        assert result == ""

    def test_python_no_deps_emits_kernel_info(self):
        result = build._notebook_meta(python_kernel=True, lakehouses=[], warehouses=[])
        assert result != ""
        data = _parse_meta_json(result)
        assert data["kernel_info"]["name"] == "jupyter"
        assert data["kernel_info"]["jupyter_kernel_name"] == "python3.12"
        assert "dependencies" not in data

    def test_pyspark_one_lakehouse(self):
        lh = [{"id": "lh-1", "name": "DATALAKE", "workspace_id": "ws-1"}]
        result = build._notebook_meta(python_kernel=False, lakehouses=lh, warehouses=[])
        data = _parse_meta_json(result)
        assert data["kernel_info"]["name"] == "synapse_pyspark"
        assert data["dependencies"]["lakehouse"]["default_lakehouse"] == "lh-1"
        assert data["dependencies"]["lakehouse"]["default_lakehouse_name"] == "DATALAKE"
        assert "warehouse" not in data["dependencies"]

    def test_pyspark_warehouse_silently_ignored(self):
        lh = [{"id": "lh-1", "name": "DATALAKE", "workspace_id": "ws-1"}]
        wh = [{"id": "wh-1", "name": "DW"}]
        result = build._notebook_meta(python_kernel=False, lakehouses=lh, warehouses=wh)
        data = _parse_meta_json(result)
        assert "warehouse" not in data.get("dependencies", {})

    def test_python_lakehouse_and_warehouse(self):
        lh = [{"id": "lh-1", "name": "DATALAKE", "workspace_id": "ws-1"}]
        wh = [{"id": "wh-1", "name": "DW"}]
        result = build._notebook_meta(python_kernel=True, lakehouses=lh, warehouses=wh)
        data = _parse_meta_json(result)
        assert data["dependencies"]["lakehouse"]["default_lakehouse"] == "lh-1"
        assert data["dependencies"]["warehouse"]["default_warehouse"] == "wh-1"

    def test_two_lakehouses_first_is_default(self):
        lh = [
            {"id": "lh-1", "name": "DATALAKE", "workspace_id": "ws-1"},
            {"id": "lh-2", "name": "BRONZE", "workspace_id": "ws-1"},
        ]
        result = build._notebook_meta(python_kernel=False, lakehouses=lh, warehouses=[])
        data = _parse_meta_json(result)
        assert data["dependencies"]["lakehouse"]["default_lakehouse"] == "lh-1"

    def test_two_lakehouses_both_in_known(self):
        lh = [
            {"id": "lh-1", "name": "DATALAKE", "workspace_id": "ws-1"},
            {"id": "lh-2", "name": "BRONZE", "workspace_id": "ws-1"},
        ]
        result = build._notebook_meta(python_kernel=False, lakehouses=lh, warehouses=[])
        data = _parse_meta_json(result)
        known = data["dependencies"]["lakehouse"]["known_lakehouses"]
        assert {"id": "lh-1"} in known
        assert {"id": "lh-2"} in known

    def test_warehouse_type_is_datawarehouse(self):
        lh = [{"id": "lh-1", "name": "DL", "workspace_id": "ws-1"}]
        wh = [{"id": "wh-1", "name": "DW"}]
        result = build._notebook_meta(python_kernel=True, lakehouses=lh, warehouses=wh)
        data = _parse_meta_json(result)
        known_wh = data["dependencies"]["warehouse"]["known_warehouses"]
        assert known_wh[0]["type"] == "Datawarehouse"


# ---------------------------------------------------------------------------
# _resolve_lakehouse / _resolve_warehouse — env-var resolution + legacy fallback
# ---------------------------------------------------------------------------

class TestResolveLakehouse:
    def test_sentinel_env_var(self, monkeypatch):
        monkeypatch.setenv("FABRIC_LAKEHOUSE_DATALAKE", "uuid-lh")
        monkeypatch.setenv("FABRIC_WORKSPACE_ID", "uuid-ws")
        result = build._resolve_lakehouse("DATALAKE")
        assert result == {"id": "uuid-lh", "name": "DATALAKE", "workspace_id": "uuid-ws"}

    def test_legacy_fallback_by_name_match(self, monkeypatch):
        monkeypatch.delenv("FABRIC_LAKEHOUSE_DATALAKE", raising=False)
        monkeypatch.setenv("FABRIC_LAKEHOUSE_NAME", "DATALAKE")
        monkeypatch.setenv("FABRIC_LAKEHOUSE_ID", "uuid-legacy")
        monkeypatch.setenv("FABRIC_WORKSPACE_ID", "uuid-ws")
        result = build._resolve_lakehouse("DATALAKE")
        assert result is not None
        assert result["id"] == "uuid-legacy"

    def test_legacy_fallback_case_insensitive(self, monkeypatch):
        monkeypatch.delenv("FABRIC_LAKEHOUSE_DATALAKE", raising=False)
        monkeypatch.setenv("FABRIC_LAKEHOUSE_NAME", "datalake")
        monkeypatch.setenv("FABRIC_LAKEHOUSE_ID", "uuid-legacy")
        monkeypatch.setenv("FABRIC_WORKSPACE_ID", "uuid-ws")
        result = build._resolve_lakehouse("DATALAKE")
        assert result is not None

    def test_not_found_returns_none(self, monkeypatch):
        monkeypatch.delenv("FABRIC_LAKEHOUSE_DATALAKE", raising=False)
        monkeypatch.delenv("FABRIC_LAKEHOUSE_NAME", raising=False)
        monkeypatch.delenv("FABRIC_LAKEHOUSE_ID", raising=False)
        assert build._resolve_lakehouse("DATALAKE") is None

    def test_sentinel_preferred_over_legacy(self, monkeypatch):
        monkeypatch.setenv("FABRIC_LAKEHOUSE_DATALAKE", "uuid-sentinel")
        monkeypatch.setenv("FABRIC_LAKEHOUSE_NAME", "DATALAKE")
        monkeypatch.setenv("FABRIC_LAKEHOUSE_ID", "uuid-legacy")
        monkeypatch.setenv("FABRIC_WORKSPACE_ID", "uuid-ws")
        result = build._resolve_lakehouse("DATALAKE")
        assert result["id"] == "uuid-sentinel"


class TestResolveWarehouse:
    def test_sentinel_env_var(self, monkeypatch):
        monkeypatch.setenv("FABRIC_WAREHOUSE_DATA_WAREHOUSE", "uuid-wh")
        result = build._resolve_warehouse("DATA_WAREHOUSE")
        assert result == {"id": "uuid-wh", "name": "DATA_WAREHOUSE"}

    def test_legacy_fallback(self, monkeypatch):
        monkeypatch.delenv("FABRIC_WAREHOUSE_DATA_WAREHOUSE", raising=False)
        monkeypatch.setenv("FABRIC_WAREHOUSE_ID", "uuid-legacy-wh")
        result = build._resolve_warehouse("DATA_WAREHOUSE")
        assert result is not None
        assert result["id"] == "uuid-legacy-wh"

    def test_not_found_returns_none(self, monkeypatch):
        monkeypatch.delenv("FABRIC_WAREHOUSE_DATA_WAREHOUSE", raising=False)
        monkeypatch.delenv("FABRIC_WAREHOUSE_ID", raising=False)
        assert build._resolve_warehouse("DATA_WAREHOUSE") is None


# ---------------------------------------------------------------------------
# render_notebook — end-to-end integration
# ---------------------------------------------------------------------------

class TestRenderNotebook:
    def test_starts_with_prologue(self, tmp_path, monkeypatch):
        monkeypatch.delenv("FABRIC_LAKEHOUSE_ID", raising=False)
        src = tmp_path / "nb.py"
        src.write_text("# %%\nx = 1\n", encoding="utf-8")
        result = build.render_notebook(src)
        assert result.startswith("# Fabric notebook source")

    def test_regular_cell_uses_cell_sep(self, tmp_path, monkeypatch):
        monkeypatch.delenv("FABRIC_LAKEHOUSE_ID", raising=False)
        src = tmp_path / "nb.py"
        src.write_text("# %%\nx = 1\n", encoding="utf-8")
        result = build.render_notebook(src)
        assert build.CELL_SEP in result

    def test_parameters_cell_uses_params_sep(self, tmp_path, monkeypatch):
        monkeypatch.delenv("FABRIC_LAKEHOUSE_ID", raising=False)
        src = tmp_path / "nb.py"
        src.write_text("# %% [parameters]\nWH = ''\n# %%\nx = 1\n", encoding="utf-8")
        result = build.render_notebook(src)
        assert build.PARAMS_CELL_SEP in result
        assert build.CELL_SEP in result

    def test_python_kernel_sentinel_sets_jupyter_kernel(self, tmp_path, monkeypatch):
        monkeypatch.delenv("FABRIC_LAKEHOUSE_ID", raising=False)
        src = tmp_path / "nb.py"
        src.write_text("# FABRIC_KERNEL: python\n# %%\nx = 1\n", encoding="utf-8")
        result = build.render_notebook(src)
        assert '"jupyter_kernel_name": "python3.12"' in result
        assert '"language_group": "jupyter_python"' in result

    def test_pyspark_is_default_kernel(self, tmp_path, monkeypatch):
        monkeypatch.delenv("FABRIC_LAKEHOUSE_ID", raising=False)
        src = tmp_path / "nb.py"
        src.write_text("# %%\nx = 1\n", encoding="utf-8")
        result = build.render_notebook(src)
        assert '"language_group": "synapse_pyspark"' in result

    def test_lakehouse_sentinel_resolves_from_env(self, tmp_path, monkeypatch):
        monkeypatch.setenv("FABRIC_LAKEHOUSE_DATALAKE", "uuid-lh")
        monkeypatch.setenv("FABRIC_WORKSPACE_ID", "uuid-ws")
        src = tmp_path / "nb.py"
        src.write_text("# FABRIC_LAKEHOUSE: DATALAKE\n# %%\nx = 1\n", encoding="utf-8")
        result = build.render_notebook(src)
        assert "uuid-lh" in result
        assert "uuid-ws" in result

    def test_warehouse_sentinel_python_kernel(self, tmp_path, monkeypatch):
        monkeypatch.setenv("FABRIC_WAREHOUSE_DW", "uuid-wh")
        monkeypatch.delenv("FABRIC_LAKEHOUSE_ID", raising=False)
        src = tmp_path / "nb.py"
        src.write_text(
            "# FABRIC_KERNEL: python\n# FABRIC_WAREHOUSE: DW\n# %%\nx = 1\n",
            encoding="utf-8",
        )
        result = build.render_notebook(src)
        assert "uuid-wh" in result

    def test_legacy_lakehouse_env_vars_used_when_no_sentinels(self, tmp_path, monkeypatch):
        monkeypatch.setenv("FABRIC_LAKEHOUSE_ID", "uuid-legacy")
        monkeypatch.setenv("FABRIC_LAKEHOUSE_NAME", "MyLake")
        monkeypatch.setenv("FABRIC_WORKSPACE_ID", "uuid-ws")
        src = tmp_path / "nb.py"
        src.write_text("# %%\nx = 1\n", encoding="utf-8")
        result = build.render_notebook(src)
        assert "uuid-legacy" in result

    def test_no_deps_no_notebook_meta_block(self, tmp_path, monkeypatch):
        monkeypatch.delenv("FABRIC_LAKEHOUSE_ID", raising=False)
        monkeypatch.delenv("FABRIC_WORKSPACE_ID", raising=False)
        src = tmp_path / "nb.py"
        src.write_text("# %%\nx = 1\n", encoding="utf-8")
        result = build.render_notebook(src)
        # Only cell-level META blocks, no notebook-level dependencies
        assert '"dependencies"' not in result

    def test_cell_meta_appears_after_every_cell(self, tmp_path, monkeypatch):
        monkeypatch.delenv("FABRIC_LAKEHOUSE_ID", raising=False)
        src = tmp_path / "nb.py"
        src.write_text("# %%\na = 1\n# %%\nb = 2\n", encoding="utf-8")
        result = build.render_notebook(src)
        assert result.count("# METADATA ********************") == 2
