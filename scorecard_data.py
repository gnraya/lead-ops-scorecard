"""
Data loader for the Lead Ops month-on-month scorecard dashboard.

Parses "Lead Ops Scorecard 2026.xlsx" into a clean, long-format table that the
dashboard can filter per team member.

Workbook layout (per month sheet):
  row 0  -> metric GROUP headers (merged-ish, e.g. "Productivity(L2 - 40%...)")
  row 1  -> sub headers: Login | Name | Level | (Goal|Actual|Achieved) x N | Overall | Stack Rank
  row 2+ -> one row per team member; "Name" column holds the ALIAS (e.g. qrishraj)
"""
from __future__ import annotations

import base64
import io
import os
import pandas as pd

# Default location of the workbook (same folder as this file). Used for local
# runs. On a public deployment the data is NOT in the repo; instead it is
# supplied as a base64-encoded secret (see _resolve_workbook).
DEFAULT_WORKBOOK = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "Lead Ops Scorecard 2026.xlsx"
)


def _resolve_workbook(workbook):
    """Return something pandas.read_excel accepts (a path or a BytesIO).

    Resolution order:
      1. If `workbook` is already a non-default value (explicit path/buffer), use it.
      2. Streamlit secret `scorecard_xlsx_b64` (base64 of the .xlsx)  -> BytesIO.
      3. Env var SCORECARD_XLSX_B64 (base64 of the .xlsx)             -> BytesIO.
      4. Fall back to the local DEFAULT_WORKBOOK path.

    This lets the app run locally from the real file, and run on a PUBLIC
    Streamlit deployment with the data held privately in secrets (never in the
    repo).
    """
    # An explicit buffer or a non-default path always wins.
    if not isinstance(workbook, str):
        return workbook
    if workbook != DEFAULT_WORKBOOK:
        return workbook

    b64 = None
    # Streamlit secret (only available when running inside Streamlit).
    try:
        import streamlit as st  # local import so the module works without it
        if "scorecard_xlsx_b64" in st.secrets:  # type: ignore[operator]
            b64 = str(st.secrets["scorecard_xlsx_b64"])
    except Exception:
        pass

    if not b64:
        b64 = os.environ.get("SCORECARD_XLSX_B64")

    if b64:
        return io.BytesIO(base64.b64decode(b64))

    return DEFAULT_WORKBOOK

TEAM_SHEET = "Team Details"

# Month sheet names in calendar order (as they appear in the workbook).
MONTH_ORDER = [
    "January", "February", "March", "April", "May", "June",
    "July", "Aug", "Sep", "October", "November", "December",
]

# The six scored metric groups we surface in the dashboard. We match loosely on
# the start of the group-header text so small wording changes still map.
METRIC_KEYS = [
    ("Productivity", "Productivity"),
    ("Quality", "Quality"),
    ("PKT", "PKT"),
    ("Additional Task", "Additional Task"),
    ("Process Improvements", "Process Improvements"),
    ("Schedule Adherance", "Schedule Adherence"),
]


def _clean_alias(value) -> str:
    if value is None:
        return ""
    try:
        # Treat NaN / blank cells as empty rather than the string "nan".
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    text = str(value).strip().lower()
    if text in ("", "nan", "none"):
        return ""
    return text


def _open_excel(workbook) -> pd.ExcelFile:
    """Resolve the workbook source (path / buffer / secret) into an ExcelFile.

    An ExcelFile can be read many times, which a one-shot BytesIO cannot.
    """
    return pd.ExcelFile(_resolve_workbook(workbook))


def load_team_details(workbook: str = DEFAULT_WORKBOOK) -> pd.DataFrame:
    """Return the Team Details sheet with a normalized `alias` column."""
    xl = _open_excel(workbook)
    df = pd.read_excel(xl, sheet_name=TEAM_SHEET, header=0)
    df = df.rename(columns=lambda c: str(c).strip())
    df["alias"] = df["Name"].map(_clean_alias)
    return df


def _parse_month_sheet(xl: pd.ExcelFile, sheet: str) -> pd.DataFrame:
    """Parse one month sheet into a tidy per-person DataFrame."""
    raw = pd.read_excel(xl, sheet_name=sheet, header=None)
    if raw.shape[0] < 3:
        return pd.DataFrame()

    group_row = raw.iloc[0].tolist()   # metric group headers
    sub_row = [str(v).strip() for v in raw.iloc[1].tolist()]  # Goal/Actual/Achieved...

    # Build a forward-filled group label per column so each Goal/Actual/Achieved
    # knows which metric it belongs to.
    groups = []
    current = None
    for g in group_row:
        if isinstance(g, str) and g.strip():
            current = g.strip()
        groups.append(current)

    # Locate the identity columns.
    def find_col(label):
        for i, s in enumerate(sub_row):
            if s.lower() == label.lower():
                return i
        return None

    login_i = find_col("Login")
    name_i = find_col("Name")
    level_i = find_col("Level")
    overall_i = find_col("Overall")
    stack_i = None
    for i, s in enumerate(sub_row):
        if s.lower().startswith("stack"):
            stack_i = i
            break

    # Map each metric group -> its "Achieved" column index (the weighted score).
    metric_achieved_col = {}
    for group_match, nice_name in METRIC_KEYS:
        for i, s in enumerate(sub_row):
            g = groups[i] or ""
            if g.startswith(group_match) and s.lower() == "achieved":
                metric_achieved_col[nice_name] = i
                break

    records = []
    for r in range(2, raw.shape[0]):
        row = raw.iloc[r].tolist()
        alias = _clean_alias(row[name_i]) if name_i is not None else ""
        if not alias:
            continue
        rec = {
            "month": sheet,
            "alias": alias,
            "login": row[login_i] if login_i is not None else "",
            "level": row[level_i] if level_i is not None else "",
            "overall": row[overall_i] if overall_i is not None else None,
            "stack_rank": row[stack_i] if stack_i is not None else None,
        }
        for nice_name, col_i in metric_achieved_col.items():
            rec[nice_name] = row[col_i]
        records.append(rec)

    return pd.DataFrame(records)


def load_scorecards(workbook: str = DEFAULT_WORKBOOK) -> pd.DataFrame:
    """Return a long-format DataFrame of every person's score for every month."""
    xl = _open_excel(workbook)
    month_sheets = [s for s in xl.sheet_names if s != TEAM_SHEET]

    frames = [_parse_month_sheet(xl, s) for s in month_sheets]
    frames = [f for f in frames if not f.empty]
    if not frames:
        return pd.DataFrame()

    df = pd.concat(frames, ignore_index=True)

    # Order months chronologically.
    order = {m: i for i, m in enumerate(MONTH_ORDER)}
    df["_order"] = df["month"].map(lambda m: order.get(m, 99))
    df = df.sort_values(["_order", "alias"]).drop(columns="_order").reset_index(drop=True)

    # Coerce numeric columns.
    numeric_cols = ["overall", "stack_rank"] + [n for _, n in METRIC_KEYS]
    for c in numeric_cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")

    return df


def available_aliases(workbook: str = DEFAULT_WORKBOOK) -> list[str]:
    """All aliases that appear in any month sheet."""
    df = load_scorecards(workbook)
    if df.empty:
        return []
    return sorted(df["alias"].unique().tolist())


def display_name_map(workbook: str = DEFAULT_WORKBOOK) -> dict[str, str]:
    """alias -> full name, from Team Details (falls back to login seen in sheets)."""
    mapping = {}
    try:
        team = load_team_details(workbook)
        for _, row in team.iterrows():
            if row["alias"]:
                mapping[row["alias"]] = str(row.get("Login", row["alias"]))
    except Exception:
        pass
    return mapping


if __name__ == "__main__":
    df = load_scorecards()
    print("Rows:", len(df))
    print("Columns:", list(df.columns))
    print("Aliases:", available_aliases())
    print(df.head(12).to_string())
