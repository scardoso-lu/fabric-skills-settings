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
        key = key.strip()
        val = val.strip()
        if len(val) >= 2 and val[0] in ('"', "'") and val[-1] == val[0]:
            val = val[1:-1]
        else:
            val = val.split("#")[0].strip()
        os.environ.setdefault(key, val)


def _setup_azure_auth() -> None:
    """
    Configure azure-identity for sempy.fabric authentication.

    Propagating FABRIC_CLIENT_SECRET into AZURE_CLIENT_SECRET (and therefore into all
    child process environments) would violate the principle of least privilege and could
    expose the secret to subprocesses that don't need it (S15).  Instead, we construct a
    ClientSecretCredential directly if a service-principal triple is present and install
    it as the ambient DefaultAzureCredential via the AZURE_* env vars *only when no
    AZURE_* value is already set*.  The secret is read once from the current process
    environment and never re-exported.
    """
    tenant = os.environ.get("FABRIC_TENANT_ID", "").strip()
    client_id = os.environ.get("FABRIC_CLIENT_ID", "").strip()
    client_secret = os.environ.get("FABRIC_CLIENT_SECRET", "").strip()

    # Only set non-sensitive env vars (tenant/client_id); never propagate the secret.
    for src, dst in (("FABRIC_TENANT_ID", "AZURE_TENANT_ID"), ("FABRIC_CLIENT_ID", "AZURE_CLIENT_ID")):
        if not os.environ.get(dst) and os.environ.get(src):
            os.environ[dst] = os.environ[src]

    # If a full SP triple is available and azure-identity is installed, patch the
    # DefaultAzureCredential factory to return a ClientSecretCredential directly
    # so the secret stays in-process and is never written to any environment variable.
    if tenant and client_id and client_secret:
        try:
            from azure.identity import ClientSecretCredential
            _credential = ClientSecretCredential(tenant, client_id, client_secret)
            try:
                import sempy.fabric as _sf
                if hasattr(_sf, "_token_provider"):
                    _sf._token_provider = lambda resource: _credential.get_token(resource + "/.default").token
            except Exception:
                pass
        except ImportError:
            pass


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


def _print_model(
    model_name: str,
    model_id: str,
    detail: dict,
    include_hidden: bool = False,
    include_expressions: bool = False,
) -> None:
    print(f"Semantic Model : {model_name}")
    print(f"ID             : {model_id}")
    if not include_hidden:
        print("Note: hidden columns/tables omitted. Use --include-hidden to show them.")
    if not include_expressions:
        print("Note: DAX expressions hidden. Use --include-expressions to show them.")
    print()

    tables    = detail["tables"]
    columns   = detail["columns"]
    measures  = detail["measures"]
    rels      = detail["relationships"]

    tname_col   = _col(tables,  "Name",       "name")
    thidden_col = _col(tables,  "Hidden",     "isHidden")

    col_tbl   = _col(columns, "Table Name",  "tableName")
    col_name  = _col(columns, "Column Name", "name")
    col_type  = _col(columns, "Data Type",   "dataType")
    col_hide  = _col(columns, "Hidden",      "isHidden")
    col_ctype = _col(columns, "Column Type", "columnType")
    col_expr  = _col(columns, "Expression",  "expression")

    mea_tbl  = _col(measures, "Table Name",           "tableName")
    mea_name = _col(measures, "Measure Name",          "name")
    mea_expr = _col(measures, "Measure Expression",    "expression")
    mea_fmt  = _col(measures, "Measure Format String", "formatString")
    mea_desc = _col(measures, "Measure Description",   "description")
    mea_hide = _col(measures, "Hidden",                "isHidden")

    for _, trow in tables.iterrows():
        is_hidden_table = trow.name in thidden_col.index and thidden_col[trow.name]
        if is_hidden_table and not include_hidden:
            continue
        tname  = _str(tname_col[trow.name])
        hidden = "  [hidden]" if is_hidden_table else ""
        print(f"  Table: {tname}{hidden}")

        tcols = columns[col_tbl == tname]
        for _, crow in tcols.iterrows():
            if _str(col_ctype[crow.name]) == "RowNumber":
                continue
            is_hidden_col = bool(col_hide[crow.name])
            if is_hidden_col and not include_hidden:
                continue
            cname  = _str(col_name[crow.name])
            dtype  = _str(col_type[crow.name])
            chide  = " [hidden]" if is_hidden_col else ""
            ccalc  = " [calc]"  if _str(col_ctype[crow.name]) == "Calculated" else ""
            if include_expressions:
                expr = _str(col_expr[crow.name])
                suffix = f" = {expr.strip()}" if expr else ""
            else:
                expr = _str(col_expr[crow.name])
                suffix = " = [expression hidden]" if expr else ""
            print(f"    col  {cname:<38}  {dtype:<15}{chide}{ccalc}{suffix}")

        tmeas = measures[mea_tbl == tname]
        for _, mrow in tmeas.iterrows():
            is_hidden_mea = bool(mea_hide[mrow.name]) if mrow.name in mea_hide.index else False
            if is_hidden_mea and not include_hidden:
                continue
            mname = _str(mea_name[mrow.name])
            if include_expressions:
                expr = " ".join(_str(mea_expr[mrow.name]).split())[:100]
            else:
                expr = "[expression hidden]"
            fmt  = f"  [{_str(mea_fmt[mrow.name])}]" if _str(mea_fmt[mrow.name]) else ""
            desc = f"  // {_str(mea_desc[mrow.name])}" if _str(mea_desc[mrow.name]) else ""
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
    show_p.add_argument(
        "--include-hidden", action="store_true", dest="include_hidden",
        help="Include hidden tables, columns, and measures in output (S16: off by default for data minimisation)",
    )
    show_p.add_argument(
        "--include-expressions", action="store_true", dest="include_expressions",
        help="Include DAX measure and calculated-column expressions (S16: off by default — may contain sensitive business logic)",
    )

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

    include_hidden = getattr(args, "include_hidden", False)
    include_expressions = getattr(args, "include_expressions", False)

    if args.as_json:
        tables_dict = detail["tables"].to_dict(orient="records")
        columns_dict = detail["columns"].to_dict(orient="records")
        measures_dict = detail["measures"].to_dict(orient="records")

        if not include_hidden:
            tables_dict = [t for t in tables_dict if not t.get("isHidden") and not t.get("Hidden")]
            columns_dict = [c for c in columns_dict if not c.get("isHidden") and not c.get("Hidden")]
            measures_dict = [m for m in measures_dict if not m.get("isHidden") and not m.get("Hidden")]

        if not include_expressions:
            for rec in columns_dict:
                if rec.get("expression") or rec.get("Expression"):
                    rec["expression"] = "[expression hidden]"
                    rec["Expression"] = "[expression hidden]"
            for rec in measures_dict:
                if rec.get("expression") or rec.get("Measure Expression"):
                    rec["expression"] = "[expression hidden]"
                    rec["Measure Expression"] = "[expression hidden]"

        print(json.dumps(
            {
                "model": {"name": model_name, "id": model_id},
                "tables":        tables_dict,
                "columns":       columns_dict,
                "measures":      measures_dict,
                "relationships": detail["relationships"].to_dict(orient="records"),
            },
            indent=2, default=str,
        ))
        return 0

    _print_model(model_name, model_id, detail, include_hidden=include_hidden, include_expressions=include_expressions)
    return 0


if __name__ == "__main__":
    sys.exit(main())
