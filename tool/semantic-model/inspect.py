#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["semantic-link>=0.9"]
# ///
"""Inspect Microsoft Fabric Semantic Models using sempy.fabric.

Lists semantic models in the workspace and shows their tables, columns,
measures, and relationships so agents can understand the business data model
before writing DAX queries, validating metric definitions, or mapping source
tables to Gold-layer consumption models.

Usage (from target repo root):
    python tool/semantic-model/inspect.py list
    python tool/semantic-model/inspect.py show <name-or-id>
    python tool/semantic-model/inspect.py show <name-or-id> --json

Auth: reads FABRIC_TENANT_ID, FABRIC_CLIENT_ID, FABRIC_CLIENT_SECRET from .env
and maps them to AZURE_* so azure-identity DefaultAzureCredential picks them up.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

SCRIPT_ROOT = Path(__file__).resolve().parents[2]


def _load_env(root: Path) -> None:
    env_file = root / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        val = val.split("#")[0].strip().strip('"').strip("'")
        os.environ.setdefault(key.strip(), val)


def _setup_azure_auth() -> None:
    """Map FABRIC_* credentials to AZURE_* so DefaultAzureCredential finds them."""
    mapping = {
        "FABRIC_TENANT_ID": "AZURE_TENANT_ID",
        "FABRIC_CLIENT_ID": "AZURE_CLIENT_ID",
        "FABRIC_CLIENT_SECRET": "AZURE_CLIENT_SECRET",
    }
    for src, dst in mapping.items():
        if not os.environ.get(dst) and os.environ.get(src):
            os.environ[dst] = os.environ[src]


def _require_sempy():
    try:
        import sempy.fabric as fabric
        return fabric
    except ImportError as exc:
        raise SystemExit(
            "semantic-link is required. Install: python -m pip install semantic-link"
        ) from exc


def _col(df, *candidates: str, default: str = "") -> "pd.Series":
    """Return the first matching column from a DataFrame by candidate names."""
    for name in candidates:
        if name in df.columns:
            return df[name]
    return __import__("pandas").Series([default] * len(df))


def _str(val) -> str:
    return "" if val is None or (isinstance(val, float) and __import__("math").isnan(val)) else str(val)


# ── list ─────────────────────────────────────────────────────────────────────

def _list_models(fabric, workspace_id: str) -> "pd.DataFrame":
    return fabric.list_datasets(workspace=workspace_id)


def _print_list(df) -> None:
    if df.empty:
        print("No semantic models found in this workspace.")
        return
    name_col = _col(df, "Dataset Name", "displayName", "name")
    id_col   = _col(df, "Dataset Id",   "id")
    desc_col = _col(df, "Description",  "description")
    print(f"{'Name':<45}  {'ID':<36}  Description")
    print("-" * 105)
    for _, row in df.iterrows():
        name = _str(name_col[row.name])
        mid  = _str(id_col[row.name])
        desc = _str(desc_col[row.name]).replace("\n", " ")[:55]
        print(f"{name:<45}  {mid:<36}  {desc}")


# ── show ─────────────────────────────────────────────────────────────────────

def _resolve_model(df, name_or_id: str) -> tuple[str, str]:
    """Return (dataset_name, dataset_id) for the given name or ID."""
    noi = name_or_id.lower()
    name_col = _col(df, "Dataset Name", "displayName", "name")
    id_col   = _col(df, "Dataset Id",   "id")

    matches = df[
        name_col.str.lower().eq(noi) | id_col.str.lower().eq(noi)
    ]
    if matches.empty:
        raise SystemExit(
            f"No semantic model found matching {name_or_id!r}.\n"
            "Run `python tool/semantic-model/inspect.py list` to see available models."
        )
    if len(matches) > 1:
        ids = ", ".join(id_col[matches.index].tolist())
        raise SystemExit(
            f"Multiple models match {name_or_id!r}. Disambiguate with an ID: {ids}"
        )
    row = matches.iloc[0]
    return _str(name_col[row.name]), _str(id_col[row.name])


def _fetch_detail(fabric, model_name: str, workspace_id: str) -> dict:
    tables        = fabric.list_tables(dataset=model_name, workspace=workspace_id)
    columns       = fabric.list_columns(dataset=model_name, workspace=workspace_id)
    measures      = fabric.list_measures(dataset=model_name, workspace=workspace_id)
    relationships = fabric.list_relationships(dataset=model_name, workspace=workspace_id)
    return {
        "tables":        tables,
        "columns":       columns,
        "measures":      measures,
        "relationships": relationships,
    }


def _print_model(model_name: str, model_id: str, detail: dict) -> None:
    print(f"Semantic Model : {model_name}")
    print(f"ID             : {model_id}")
    print()

    tables    = detail["tables"]
    columns   = detail["columns"]
    measures  = detail["measures"]
    rels      = detail["relationships"]

    tname_col  = _col(tables,  "Name",       "name")
    thidden_col = _col(tables, "Hidden",     "isHidden")

    col_tbl  = _col(columns, "Table Name",  "tableName")
    col_name = _col(columns, "Column Name", "name")
    col_type = _col(columns, "Data Type",   "dataType")
    col_hide = _col(columns, "Hidden",      "isHidden")
    col_ctype = _col(columns, "Column Type","columnType")
    col_expr = _col(columns, "Expression",  "expression")

    mea_tbl  = _col(measures, "Table Name",        "tableName")
    mea_name = _col(measures, "Measure Name",       "name")
    mea_expr = _col(measures, "Measure Expression", "expression")
    mea_fmt  = _col(measures, "Measure Format String", "formatString")
    mea_desc = _col(measures, "Measure Description",   "description")

    for _, trow in tables.iterrows():
        tname  = _str(tname_col[trow.name])
        hidden = "  [hidden]" if trow.name in thidden_col.index and thidden_col[trow.name] else ""
        print(f"  Table: {tname}{hidden}")

        tcols = columns[col_tbl == tname]
        for _, crow in tcols.iterrows():
            if _str(col_ctype[crow.name]) == "RowNumber":
                continue
            cname  = _str(col_name[crow.name])
            dtype  = _str(col_type[crow.name])
            chide  = " [hidden]" if col_hide[crow.name] else ""
            ccalc  = " [calc]"  if _str(col_ctype[crow.name]) == "Calculated" else ""
            expr   = _str(col_expr[crow.name])
            suffix = f" = {expr.strip()}" if expr else ""
            print(f"    col  {cname:<38}  {dtype:<15}{chide}{ccalc}{suffix}")

        tmeas = measures[mea_tbl == tname]
        for _, mrow in tmeas.iterrows():
            mname = _str(mea_name[mrow.name])
            expr  = " ".join(_str(mea_expr[mrow.name]).split())[:100]
            fmt   = f"  [{_str(mea_fmt[mrow.name])}]" if _str(mea_fmt[mrow.name]) else ""
            desc  = f"  // {_str(mea_desc[mrow.name])}" if _str(mea_desc[mrow.name]) else ""
            print(f"    mea  {mname:<38}  {expr}{fmt}{desc}")
        print()

    if not rels.empty:
        from_tbl  = _col(rels, "From Table",             "fromTable")
        from_col  = _col(rels, "From Column",            "fromColumn")
        to_tbl    = _col(rels, "To Table",               "toTable")
        to_col    = _col(rels, "To Column",              "toColumn")
        is_active = _col(rels, "Is Active",              "isActive")
        cross_flt = _col(rels, "Cross Filtering Behavior","crossFilteringBehavior")

        print("  Relationships:")
        for _, rrow in rels.iterrows():
            active = "" if is_active[rrow.name] else "  [inactive]"
            cross  = f"  [{_str(cross_flt[rrow.name])}]" if _str(cross_flt[rrow.name]) else ""
            print(
                f"    {_str(from_tbl[rrow.name])}[{_str(from_col[rrow.name])}]"
                f"  →  {_str(to_tbl[rrow.name])}[{_str(to_col[rrow.name])}]"
                f"{cross}{active}"
            )


# ── main ─────────────────────────────────────────────────────────────────────

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--workspace", help="Workspace ID (overrides FABRIC_WORKSPACE_ID in .env)")
    sub = ap.add_subparsers(dest="command", required=True)
    sub.add_parser("list", help="List all semantic models in the workspace")
    show_p = sub.add_parser(
        "show", help="Show tables, columns, measures, and relationships for a model"
    )
    show_p.add_argument("model", help="Semantic model display name or ID")
    show_p.add_argument("--json", action="store_true", dest="as_json", help="Output raw JSON")

    args = ap.parse_args(argv)
    _load_env(SCRIPT_ROOT)
    _setup_azure_auth()

    workspace_id = (args.workspace or os.environ.get("FABRIC_WORKSPACE_ID", "")).strip()
    if not workspace_id:
        raise SystemExit(
            "FABRIC_WORKSPACE_ID is not set. Add it to .env or pass --workspace."
        )

    fabric = _require_sempy()
    models = _list_models(fabric, workspace_id)

    if args.command == "list":
        _print_list(models)
        return 0

    model_name, model_id = _resolve_model(models, args.model)
    detail = _fetch_detail(fabric, model_name, workspace_id)

    if args.as_json:
        print(json.dumps(
            {
                "model": {"name": model_name, "id": model_id},
                "tables":        detail["tables"].to_dict(orient="records"),
                "columns":       detail["columns"].to_dict(orient="records"),
                "measures":      detail["measures"].to_dict(orient="records"),
                "relationships": detail["relationships"].to_dict(orient="records"),
            },
            indent=2, default=str,
        ))
        return 0

    _print_model(model_name, model_id, detail)
    return 0


if __name__ == "__main__":
    sys.exit(main())
