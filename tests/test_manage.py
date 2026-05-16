"""Regression tests for tool/pipeline/manage.py.

Pure-function tests require no live Fabric workspace. Tests that exercise
cmd_* functions mock fab_api so no network call is made.
"""
import json
import uuid
from unittest.mock import MagicMock, patch

import pytest

import manage


# ---------------------------------------------------------------------------
# _parse_params — KEY=VALUE,... string → dict
# ---------------------------------------------------------------------------

class TestParseParams:
    def test_none_returns_empty(self):
        assert manage._parse_params(None) == {}

    def test_empty_string_returns_empty(self):
        assert manage._parse_params("") == {}

    def test_single_pair(self):
        assert manage._parse_params("KEY=VALUE") == {"KEY": "VALUE"}

    def test_multiple_pairs(self):
        result = manage._parse_params("KEY=VALUE,KEY2=VALUE2")
        assert result == {"KEY": "VALUE", "KEY2": "VALUE2"}

    def test_value_with_equals_sign(self):
        # partition on first = only — remainder goes to value
        result = manage._parse_params("KEY=VAL=UE")
        assert result == {"KEY": "VAL=UE"}

    def test_item_without_equals_skipped(self):
        result = manage._parse_params("NOEQUALS,KEY=VALUE")
        assert result == {"KEY": "VALUE"}

    def test_whitespace_around_key_and_value_stripped(self):
        result = manage._parse_params("KEY = VALUE")
        assert result == {"KEY": "VALUE"}

    def test_url_value_preserved(self):
        result = manage._parse_params("HOST=db.example.com")
        assert result["HOST"] == "db.example.com"


# ---------------------------------------------------------------------------
# _read_topic_params — pipeline_params.json → dict[str, str]
# ---------------------------------------------------------------------------

class TestReadTopicParams:
    def test_missing_file_returns_empty(self, tmp_path, monkeypatch):
        monkeypatch.setattr(manage, "SCRIPT_ROOT", tmp_path)
        assert manage._read_topic_params("my_topic") == {}

    def test_reads_parameters_key(self, tmp_path, monkeypatch):
        monkeypatch.setattr(manage, "SCRIPT_ROOT", tmp_path)
        d = tmp_path / "workspace" / "my_topic"
        d.mkdir(parents=True)
        (d / "pipeline_params.json").write_text(
            json.dumps({"parameters": {"HOST": "example.com", "SCHEMA": "dbo"}}),
            encoding="utf-8",
        )
        result = manage._read_topic_params("my_topic")
        assert result == {"HOST": "example.com", "SCHEMA": "dbo"}

    def test_all_values_coerced_to_str(self, tmp_path, monkeypatch):
        monkeypatch.setattr(manage, "SCRIPT_ROOT", tmp_path)
        d = tmp_path / "workspace" / "topic"
        d.mkdir(parents=True)
        (d / "pipeline_params.json").write_text(
            json.dumps({"parameters": {"NUM": 42, "FLAG": True, "EMPTY": ""}}),
            encoding="utf-8",
        )
        result = manage._read_topic_params("topic")
        assert result["NUM"] == "42"
        assert result["FLAG"] == "True"
        assert result["EMPTY"] == ""

    def test_missing_parameters_key_returns_empty(self, tmp_path, monkeypatch):
        monkeypatch.setattr(manage, "SCRIPT_ROOT", tmp_path)
        d = tmp_path / "workspace" / "topic"
        d.mkdir(parents=True)
        (d / "pipeline_params.json").write_text(json.dumps({}), encoding="utf-8")
        assert manage._read_topic_params("topic") == {}


# ---------------------------------------------------------------------------
# _order_weight — notebook ordering by prefix
# ---------------------------------------------------------------------------

class TestOrderWeight:
    def test_download_is_first(self):
        assert manage._order_weight("download_orders") == 0

    def test_bronze_is_second(self):
        assert manage._order_weight("bronze_orders") == 1

    def test_dq_bronze_is_third(self):
        assert manage._order_weight("dq_bronze_orders") == 2

    def test_silver_is_fourth(self):
        assert manage._order_weight("silver_orders") == 3

    def test_dq_silver_is_fifth(self):
        assert manage._order_weight("dq_silver_orders") == 4

    def test_gold_is_sixth(self):
        assert manage._order_weight("gold_orders") == 5

    def test_dq_gold_is_seventh(self):
        assert manage._order_weight("dq_gold_orders") == 6

    def test_unknown_prefix_is_last(self):
        assert manage._order_weight("utility_helper") == len(manage._NOTEBOOK_ORDER)

    def test_matching_is_case_insensitive(self):
        assert manage._order_weight("DOWNLOAD_orders") == 0


# ---------------------------------------------------------------------------
# _build_pipeline_content — pipeline JSON structure
# ---------------------------------------------------------------------------

NOTEBOOKS = [
    {"id": "nb-1", "displayName": "download_orders"},
    {"id": "nb-2", "displayName": "bronze_orders"},
]


class TestBuildPipelineContent:
    def _parse(self, **kwargs) -> dict:
        return json.loads(manage._build_pipeline_content("p", "ws-1", NOTEBOOKS, **kwargs))

    def test_pipeline_name(self):
        data = self._parse()
        assert data["name"] == "p"

    def test_activity_count(self):
        data = self._parse()
        assert len(data["properties"]["activities"]) == 2

    def test_first_activity_no_depends_on(self):
        data = self._parse()
        assert data["properties"]["activities"][0]["dependsOn"] == []

    def test_second_depends_on_first(self):
        activities = self._parse()["properties"]["activities"]
        deps = activities[1]["dependsOn"]
        assert len(deps) == 1
        assert deps[0]["activity"] == activities[0]["name"]
        assert "Succeeded" in deps[0]["dependencyConditions"]

    def test_notebook_ids_match(self):
        activities = self._parse()["properties"]["activities"]
        for i, act in enumerate(activities):
            assert act["typeProperties"]["notebookId"] == NOTEBOOKS[i]["id"]

    def test_workspace_id_embedded(self):
        activities = self._parse()["properties"]["activities"]
        for act in activities:
            assert act["typeProperties"]["workspaceId"] == "ws-1"

    def test_no_params_no_parameters_key(self):
        activities = self._parse(params=None)["properties"]["activities"]
        for act in activities:
            assert "parameters" not in act["typeProperties"]

    def test_params_embedded_in_every_activity(self):
        params = {"HOST": "db.example.com", "SCHEMA": "dbo"}
        activities = self._parse(params=params)["properties"]["activities"]
        for act in activities:
            tp = act["typeProperties"]["parameters"]
            assert tp["HOST"] == {"value": "db.example.com", "type": "string"}
            assert tp["SCHEMA"] == {"value": "dbo", "type": "string"}

    def test_params_type_is_always_string(self):
        activities = self._parse(params={"N": "42"})["properties"]["activities"]
        assert activities[0]["typeProperties"]["parameters"]["N"]["type"] == "string"

    def test_activity_names_use_display_name(self):
        activities = self._parse()["properties"]["activities"]
        assert activities[0]["name"] == "run_download_orders"
        assert activities[1]["name"] == "run_bronze_orders"


# ---------------------------------------------------------------------------
# _build_platform_file — deterministic UUID logicalId
# ---------------------------------------------------------------------------

class TestBuildPlatformFile:
    def _parse(self, name: str = "pipeline_orders") -> dict:
        return json.loads(manage._build_platform_file(name))

    def test_metadata_type(self):
        assert self._parse()["metadata"]["type"] == "DataPipeline"

    def test_metadata_display_name(self):
        assert self._parse("my_pipeline")["metadata"]["displayName"] == "my_pipeline"

    def test_schema_url_present(self):
        assert "json-schemas" in self._parse()["$schema"]

    def test_logical_id_is_valid_uuid(self):
        logical_id = self._parse()["config"]["logicalId"]
        uuid.UUID(logical_id)  # raises ValueError if invalid

    def test_logical_id_is_not_zeroed(self):
        logical_id = self._parse()["config"]["logicalId"]
        assert logical_id != "00000000-0000-0000-0000-000000000000"

    def test_logical_id_is_deterministic(self):
        a = self._parse("pipeline_orders")
        b = self._parse("pipeline_orders")
        assert a["config"]["logicalId"] == b["config"]["logicalId"]

    def test_different_names_yield_different_ids(self):
        a = self._parse("pipeline_orders")["config"]["logicalId"]
        b = self._parse("pipeline_energy")["config"]["logicalId"]
        assert a != b

    def test_logical_id_matches_uuid5_formula(self):
        expected = str(uuid.uuid5(manage._LOGICAL_ID_NAMESPACE, "pipeline_orders"))
        actual = self._parse("pipeline_orders")["config"]["logicalId"]
        assert actual == expected


# ---------------------------------------------------------------------------
# _parse_params + _read_topic_params merge — CLI overrides file values
# ---------------------------------------------------------------------------

class TestParamsMerge:
    def test_cli_overrides_file_value(self, tmp_path, monkeypatch):
        monkeypatch.setattr(manage, "SCRIPT_ROOT", tmp_path)
        d = tmp_path / "workspace" / "topic"
        d.mkdir(parents=True)
        (d / "pipeline_params.json").write_text(
            json.dumps({"parameters": {"HOST": "default.host", "SCHEMA": "dbo"}}),
            encoding="utf-8",
        )
        file_params = manage._read_topic_params("topic")
        cli_params = manage._parse_params("HOST=override.host")
        merged = {**file_params, **cli_params}
        assert merged["HOST"] == "override.host"
        assert merged["SCHEMA"] == "dbo"

    def test_file_params_used_when_no_cli(self, tmp_path, monkeypatch):
        monkeypatch.setattr(manage, "SCRIPT_ROOT", tmp_path)
        d = tmp_path / "workspace" / "topic"
        d.mkdir(parents=True)
        (d / "pipeline_params.json").write_text(
            json.dumps({"parameters": {"HOST": "file.host"}}),
            encoding="utf-8",
        )
        file_params = manage._read_topic_params("topic")
        merged = {**file_params, **manage._parse_params(None)}
        assert merged == {"HOST": "file.host"}


# ---------------------------------------------------------------------------
# cmd_create — mocked fab_api
# ---------------------------------------------------------------------------

def _make_fab_response(value: dict | None = None, headers: dict | None = None) -> dict:
    return {
        "status": "Success",
        "result": {
            "data": [
                {
                    "text": value or {},
                    "headers": headers or {},
                }
            ]
        },
    }


class TestCmdCreate:
    def test_creates_new_pipeline(self):
        workspace_id = "ws-1"
        # _discover_notebooks filters on type == "Notebook"
        notebooks = [{"id": "nb-1", "displayName": "download_orders", "type": "Notebook"}]
        created_pipeline = {"id": "pl-1", "displayName": "pipeline_orders", "type": "DataPipeline"}

        list_call_count = 0

        def controlled_list(workspace_id_arg):
            nonlocal list_call_count
            list_call_count += 1
            if list_call_count == 1:
                # _discover_notebooks: return the notebook
                return notebooks
            if list_call_count == 2:
                # _find_item for existing pipeline: not present yet
                return notebooks
            # _find_item after create succeeds: return pipeline
            return [*notebooks, created_pipeline]

        def fake_fab_api(endpoint, method="get", body=None, show_headers=False):
            return _make_fab_response({})

        with (
            patch.object(manage, "fab_api", side_effect=fake_fab_api),
            patch.object(manage, "_list_workspace_items", side_effect=controlled_list),
        ):
            result = manage.cmd_create(workspace_id, "orders", None)

        assert result == "pl-1"

    def test_updates_existing_pipeline(self):
        workspace_id = "ws-1"
        notebooks = [{"id": "nb-1", "displayName": "download_orders", "type": "Notebook"}]
        existing_pipeline = {
            "id": "pl-existing",
            "displayName": "pipeline_orders",
            "type": "DataPipeline",
        }

        call_count = 0

        def controlled_list(workspace_id_arg):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # _discover_notebooks
                return notebooks
            # _find_item: pipeline already exists
            return [*notebooks, existing_pipeline]

        update_called = []

        def fake_fab_api(endpoint, method="get", body=None, show_headers=False):
            if "updateDefinition" in endpoint and method == "post":
                update_called.append(endpoint)
            return _make_fab_response({})

        with (
            patch.object(manage, "fab_api", side_effect=fake_fab_api),
            patch.object(manage, "_list_workspace_items", side_effect=controlled_list),
        ):
            result = manage.cmd_create(workspace_id, "orders", None)

        assert result == "pl-existing"
        assert len(update_called) == 1


# ---------------------------------------------------------------------------
# CLI: run subparser has no --params argument
# ---------------------------------------------------------------------------

class TestCliRunSubparser:
    def test_run_does_not_accept_params(self):
        import argparse
        ap = argparse.ArgumentParser()
        sub = ap.add_subparsers(dest="command")
        p_run = sub.add_parser("run")
        p_run.add_argument("--pipeline", required=True)
        # Confirm the actual manage module's parser doesn't expose --params on run
        # by checking the source directly
        import ast
        import pathlib
        src = (pathlib.Path(manage.__file__)).read_text(encoding="utf-8")
        tree = ast.parse(src)
        # Find all add_argument calls on p_run
        in_p_run_block = False
        found_params_on_run = False
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for t in node.targets:
                    if isinstance(t, ast.Name) and t.id == "p_run":
                        in_p_run_block = True
        # Simple text search: --params must not appear after p_run definition
        # before the next sub.add_parser call
        lines = src.splitlines()
        in_run = False
        for line in lines:
            if "p_run = sub.add_parser" in line:
                in_run = True
            elif in_run and "sub.add_parser" in line:
                break
            elif in_run and '"--params"' in line:
                found_params_on_run = True
                break
        assert not found_params_on_run, "p_run must not register --params"
