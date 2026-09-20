"""Validate replication evidence and render a standalone audit report."""

from __future__ import annotations

import base64
import html
import json
import os
import tempfile
from pathlib import Path
from typing import Any, Iterable

from .errors import ReportError


REQUIRED_KEYS = {
    "paper",
    "run",
    "summary",
    "metrics",
    "methodology",
    "assumptions",
    "fidelity_gaps",
    "figures",
    "tables",
}
METHODOLOGY_STATUSES = {
    "matched",
    "adapted",
    "extended",
    "unavailable",
    "unresolved",
}
SUCCESS_STATUSES = {"matched", "adapted", "extended"}


def validate_payload(payload: dict[str, Any]) -> None:
    if not isinstance(payload, dict):
        raise ReportError("Report payload must be a JSON object.")
    missing = sorted(REQUIRED_KEYS - payload.keys())
    if missing:
        raise ReportError("Report payload is missing keys: " + ", ".join(missing))
    if not isinstance(payload["paper"], dict) or not isinstance(payload["run"], dict):
        raise ReportError("paper and run must be objects.")
    if payload["run"].get("status") not in SUCCESS_STATUSES:
        raise ReportError("A published run must have status matched, adapted, or extended.")
    for key in ("metrics", "methodology", "assumptions", "fidelity_gaps", "figures", "tables"):
        if not isinstance(payload[key], list):
            raise ReportError(f"'{key}' must be a list.")
    for index, row in enumerate(payload["methodology"]):
        if not isinstance(row, dict):
            raise ReportError(f"methodology[{index}] must be an object.")
        if row.get("Status") not in METHODOLOGY_STATUSES:
            raise ReportError(
                f"methodology[{index}].Status must use the controlled vocabulary."
            )


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", newline="\n", delete=False, dir=path.parent
        ) as handle:
            temporary_name = handle.name
            handle.write(content)
        os.replace(temporary_name, path)
    except OSError as exc:
        if temporary_name:
            Path(temporary_name).unlink(missing_ok=True)
        raise ReportError(f"Cannot write report artifact '{path}': {exc}") from exc


def write_payload(payload: dict[str, Any], path: Path) -> None:
    validate_payload(payload)
    try:
        content = json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    except (TypeError, ValueError) as exc:
        raise ReportError(f"Report payload is not valid JSON: {exc}") from exc
    _atomic_write(path, content)


def load_payload(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ReportError(f"Report payload not found: {path}") from exc
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ReportError(f"Cannot read report payload '{path}': {exc}") from exc
    validate_payload(payload)
    return payload


def _table(rows: Iterable[dict[str, Any]]) -> str:
    rows = list(rows)
    if not rows:
        return '<p class="unavailable">unavailable</p>'
    columns: list[str] = []
    for row in rows:
        for key in row:
            if key not in columns:
                columns.append(key)
    head = "".join(f"<th>{html.escape(column)}</th>" for column in columns)
    body = "".join(
        "<tr>"
        + "".join(f"<td>{html.escape(str(row.get(column, 'unavailable')))}</td>" for column in columns)
        + "</tr>"
        for row in rows
    )
    return f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"


def _figures(items: list[dict[str, Any]], project_root: Path) -> str:
    if not items:
        return '<p class="unavailable">unavailable</p>'
    rendered: list[str] = []
    for index, item in enumerate(items):
        if not isinstance(item, dict) or not item.get("path"):
            raise ReportError(f"figures[{index}] must contain a path.")
        path = Path(str(item["path"]))
        source = path if path.is_absolute() else project_root / path
        source = source.resolve()
        try:
            source.relative_to(project_root.resolve())
        except ValueError as exc:
            raise ReportError(f"Figure must stay inside project: {path}") from exc
        try:
            encoded = base64.b64encode(source.read_bytes()).decode("ascii")
        except OSError as exc:
            raise ReportError(f"Cannot embed figure '{path}': {exc}") from exc
        suffix = source.suffix.lower().lstrip(".")
        mime = "image/jpeg" if suffix in {"jpg", "jpeg"} else f"image/{suffix or 'png'}"
        title = html.escape(str(item.get("title", source.stem)))
        alt = html.escape(str(item.get("alt", title)))
        rendered.append(
            f'<figure><img src="data:{mime};base64,{encoded}" alt="{alt}">'
            f"<figcaption>{title}</figcaption></figure>"
        )
    return "".join(rendered)


def _result_tables(items: list[dict[str, Any]]) -> str:
    if not items:
        return '<p class="unavailable">unavailable</p>'
    rendered: list[str] = []
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            raise ReportError(f"tables[{index}] must be an object.")
        columns = item.get("columns", [])
        rows = item.get("rows", [])
        if not isinstance(columns, list) or not isinstance(rows, list):
            raise ReportError(f"tables[{index}] columns and rows must be lists.")
        mapped = [dict(zip(columns, row)) for row in rows]
        rendered.append(f"<h3>{html.escape(str(item.get('title', 'Table')))}</h3>{_table(mapped)}")
    return "".join(rendered)


def render_report(payload: dict[str, Any], path: Path, project_root: Path) -> None:
    validate_payload(payload)
    paper = payload["paper"]
    run = payload["run"]
    assumptions = "".join(f"<li>{html.escape(str(item))}</li>" for item in payload["assumptions"])
    gaps = "".join(f"<li>{html.escape(str(item))}</li>" for item in payload["fidelity_gaps"])
    document = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(str(paper.get('title', 'Replication report')))}</title>
<style>body{{font:16px/1.55 system-ui,sans-serif;max-width:1100px;margin:auto;padding:2rem;color:#172033}}h1,h2{{color:#103b66}}table{{border-collapse:collapse;width:100%;margin:1rem 0}}th,td{{border:1px solid #ccd4dd;padding:.55rem;text-align:left}}th{{background:#edf3f8}}img{{max-width:100%;height:auto}}.unavailable{{color:#7a2931}}code{{background:#f3f5f7;padding:.15rem .3rem}}</style></head><body>
<h1>{html.escape(str(paper.get('title', 'Replication report')))}</h1>
<h2>Executive Summary</h2><p>{html.escape(str(payload['summary']))}</p>
<p><strong>Status:</strong> {html.escape(str(run.get('status', 'unavailable')))} · <strong>Mode:</strong> {html.escape(str(run.get('mode', 'unavailable')))} · <strong>Sample:</strong> {html.escape(str(run.get('sample', 'unavailable')))}</p>
<h2>Headline Metrics</h2>{_table(payload['metrics'])}
<h2>Figures and Result Tables</h2>{_figures(payload['figures'], project_root)}{_result_tables(payload['tables'])}
<h2>Methodology Mapping</h2>{_table(payload['methodology'])}
<h2>Data and Assumptions</h2><ul>{assumptions or '<li>unavailable</li>'}</ul>
<h2>Fidelity Gaps and Limitations</h2><ul>{gaps or '<li>unavailable</li>'}</ul>
<h2>Reproducibility</h2><p><strong>Generated:</strong> {html.escape(str(run.get('generated_at', 'unavailable')))}<br><strong>Commit:</strong> {html.escape(str(run.get('commit_sha', 'unavailable')))}<br><strong>Command:</strong> <code>{html.escape(str(run.get('command', 'unavailable')))}</code></p>
<p><em>Research output only; not investment advice.</em></p></body></html>"""
    _atomic_write(path, document)
