"""
tools.py - Sage data layer (dataset-agnostic)

Loads ANY CSV/Excel into SQLite + a pandas DataFrame, profiles columns
generically, exposes LangChain tools the agent uses to answer questions
about whatever the user uploaded. No hardcoded business columns.

State is scoped per-session (SessionData) rather than at module level, so
concurrent users each get their own dataframe, SQLite table, and profile
cache instead of silently sharing (and overwriting) one global dataset.
"""

from __future__ import annotations

import json
import os
import re
import sqlite3
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from langchain_core.tools import tool


# ============================================================================
# Per-session state
# ============================================================================
# Each session's cleaned data lives in its own SQLite file under this
# directory (next to the code, NOT the OS temp dir) so it survives a
# process restart. Add this directory to .gitignore; on a host with an
# ephemeral filesystem (e.g. a fresh container redeploy with no attached
# volume) it still won't survive a full redeploy — that needs a persistent
# volume mounted at this path.
SESSION_DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "session_data")
os.makedirs(SESSION_DATA_DIR, exist_ok=True)


class SessionData:
    """Holds one uploaded dataset's cleaned dataframe, SQLite table, and
    cached profile. One instance per session_id — never shared across
    sessions/users, so concurrent uploads can't clobber each other."""

    def __init__(self, session_id: str):
        self.session_id = session_id
        self.df: Optional[pd.DataFrame] = None
        self.db_path: str = os.path.join(SESSION_DATA_DIR, f"sage_{session_id}.db")
        self.table_name: str = "data"
        self.cleaning_report: List[str] = []
        self.profile_cache: Optional[Dict[str, Any]] = None
        self.dataset_name: Optional[str] = None


# ============================================================================
# Smart Excel reader — auto-detect header row
# ============================================================================
def smart_read_excel(file_buffer) -> pd.DataFrame:
    """Read an Excel file, auto-detecting the actual header row.
    Scans first 20 rows, picks the row with the most non-null text cells
    that is immediately followed by a data row with numeric values.
    """
    raw = pd.read_excel(file_buffer, header=None, nrows=20)
    header_row = 0
    best_score = -1
    for i in range(len(raw) - 1):
        row = raw.iloc[i].astype(str).str.strip()
        next_row = raw.iloc[i + 1].astype(str).str.strip()
        # Score = text cells in this row + numeric cells in next row
        text_count = (
            (row.str.lower() != "nan") &
            (pd.to_numeric(row, errors="coerce").isna())
        ).sum()
        next_numeric = pd.to_numeric(
            next_row.str.replace(r"[\$,€£¥%\s]", "", regex=True),
            errors="coerce"
        ).notna().sum()
        score = text_count * 2 + next_numeric
        if score > best_score:
            best_score = score
            header_row = i
    file_buffer.seek(0)
    df = pd.read_excel(file_buffer, header=header_row)
    return df.dropna(axis=1, how="all").dropna(axis=0, how="all")


# ============================================================================
# Generic cleaning
# ============================================================================
_NUM_STRIP_RE = re.compile(r"[\$,€£¥%\s]")


def _slugify(name: str) -> str:
    s = str(name).strip().lower()
    s = re.sub(r"[^\w]+", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    return s or "col"


def _looks_numeric(series: pd.Series, threshold: float = 0.8) -> bool:
    sample = series.dropna().astype(str).head(50)
    if sample.empty:
        return False
    cleaned = sample.str.replace(_NUM_STRIP_RE, "", regex=True)
    parsed = pd.to_numeric(cleaned, errors="coerce")
    return parsed.notna().mean() >= threshold


def _looks_datetime(series: pd.Series, threshold: float = 0.8) -> bool:
    sample = series.dropna().astype(str).head(50)
    if sample.empty:
        return False
    parsed = pd.to_datetime(sample, errors="coerce", utc=False)
    return parsed.notna().mean() >= threshold


def clean_dataframe(df: pd.DataFrame) -> Tuple[pd.DataFrame, List[str]]:
    """Generic cleaning. Returns (cleaned_df, human_readable_changes)."""
    changes: List[str] = []
    df = df.copy()

    original_cols = list(df.columns)
    df.columns = [_slugify(c) for c in df.columns]
    renamed = [(o, n) for o, n in zip(original_cols, df.columns) if str(o).strip() != n]
    if renamed:
        changes.append(f"Normalised {len(renamed)} column name(s) for SQL safety")

    before_rows = len(df)
    df = df.dropna(axis=1, how="all").dropna(axis=0, how="all")
    if len(df) < before_rows:
        changes.append(f"Removed {before_rows - len(df)} empty row(s)")

    converted_numeric: List[str] = []
    for col in df.columns:
        if pd.api.types.is_string_dtype(df[col]) and _looks_numeric(df[col]):
            df[col] = pd.to_numeric(
                df[col].astype(str).str.replace(_NUM_STRIP_RE, "", regex=True),
                errors="coerce",
            )
            converted_numeric.append(col)
    if converted_numeric:
        more = "..." if len(converted_numeric) > 6 else ""
        changes.append(f"Converted {len(converted_numeric)} column(s) to numeric: " + ", ".join(converted_numeric[:6]) + more)

    parsed_dates: List[str] = []
    for col in df.columns:
        if pd.api.types.is_string_dtype(df[col]) and _looks_datetime(df[col]):
            df[col] = pd.to_datetime(df[col], errors="coerce")
            parsed_dates.append(col)
    if parsed_dates:
        changes.append(f"Parsed {len(parsed_dates)} date column(s): " + ", ".join(parsed_dates))

    for col in df.columns:
        if pd.api.types.is_string_dtype(df[col]):
            df[col] = df[col].astype(str).str.strip()

    return df, changes


# ============================================================================
# Column classification
# ============================================================================
_ID_NAME_RE = re.compile(
    r"(?:^|[_\-\s])(id|code|key|uuid|guid|sku)($|[_\-\s])"  # snake_case: customer_id
    r"|ID$"                                                     # camelCase suffix: CustomerID
    r"|^(id|code|key)$",                                       # bare: 'id', 'code', 'key'
    re.I
)

_NAME_COL_RE = re.compile(
    r"(first|last|full|middle|given|sur|family)?[_\-\s]?name"
    r"|salutation|prefix|suffix|title",
    re.I
)

# Numeric columns whose NAME marks them as a label/location/identifier tag
# (which room, which zip code, which gate) rather than a measurement —
# these repeat by nature, so uniqueness doesn't apply to them.
_ID_LABEL_WORDS = ("room", "zip", "postal", "phone", "floor", "seat", "gate", "bed", "ward", "label")


def _looks_like_sequence(s: pd.Series) -> bool:
    """True if values are essentially a contiguous, near-unique sequence
    (e.g. 1,2,3... — an auto-increment ID)."""
    vals = pd.to_numeric(s, errors="coerce").dropna()
    if len(vals) < 20:
        return False
    # A real ID sequence has little to no repetition. Without this check,
    # any ordinary numeric column with a lot of duplicate values (Age,
    # Length of Stay, ratings, etc.) sorts into long runs of diff == 0,
    # which would otherwise dominate the mode and get misread as "sequential".
    if vals.nunique() < 0.9 * len(vals):
        return False
    diffs = vals.sort_values().diff().dropna()
    if diffs.empty:
        return False
    mode_diff = diffs.mode().iloc[0]
    # A sequence steps forward by a small constant amount. A mode diff of 0
    # means the column is full of duplicates sitting next to each other once
    # sorted — that's the opposite of an incrementing sequence.
    if mode_diff <= 0:
        return False
    return float((diffs == mode_diff).mean()) > 0.9


def _classify_columns(df: pd.DataFrame) -> Dict[str, List[str]]:
    """Classify columns into numeric / categorical / datetime / text / id.

    A column is flagged as 'id' when its NAME looks like an identifier
    (contains id/code/key/uuid/guid/sku) AND uniqueness is high, when its
    name marks it as a label/location tag (room, zip, phone, ...) regardless
    of uniqueness, or when its values form a near-perfect increasing
    sequence. Random high-uniqueness numerics like Salary or Revenue stay
    as 'numeric'.
    """
    out: Dict[str, List[str]] = {
        "numeric": [], "datetime": [], "categorical": [], "text": [], "id": [],
    }
    n = max(len(df), 1)
    for col in df.columns:
        s = df[col]
        if pd.api.types.is_datetime64_any_dtype(s):
            out["datetime"].append(col)
        elif pd.api.types.is_numeric_dtype(s):
            unique_ratio = s.nunique(dropna=True) / n
            name_looks_id = bool(_ID_NAME_RE.search(str(col)))
            name_looks_label = any(w in str(col).lower() for w in _ID_LABEL_WORDS)
            is_sequence = pd.api.types.is_integer_dtype(s) and _looks_like_sequence(s)
            if (name_looks_id and unique_ratio > 0.9) or name_looks_label or is_sequence:
                out["id"].append(col)
            else:
                out["numeric"].append(col)
        else:
            unique_ratio = s.nunique(dropna=True) / n
            name_col = bool(_NAME_COL_RE.search(str(col)))
            if name_col or (unique_ratio > 0.6 and n > 30):
                out["text"].append(col)
            else:
                out["categorical"].append(col)
    return out


def build_profile(df: pd.DataFrame, cleaning_report: Optional[List[str]] = None) -> Dict[str, Any]:
    """Pure function of `df` (plus the cleaning-change log that produced it,
    if any) — no hidden module/session state, so it's safe to call from
    anywhere with any dataframe."""
    classes = _classify_columns(df)

    numeric_summary: Dict[str, Any] = {}
    for col in classes["numeric"]:
        # Skip ID-like columns — summing/averaging them is meaningless
        if col in classes.get("id", []):
            continue
        s = pd.to_numeric(df[col], errors="coerce").dropna()
        if len(s) == 0:
            continue
        numeric_summary[col] = {
            "count": int(len(s)),
            "min": round(float(s.min()), 4),
            "max": round(float(s.max()), 4),
            "mean": round(float(s.mean()), 4),
            "median": round(float(s.median()), 4),
            "sum": round(float(s.sum()), 4),
            "std": round(float(s.std() or 0), 4),
        }

    categorical_summary: Dict[str, Any] = {}
    for col in classes["categorical"]:
        vc = df[col].value_counts(dropna=True).head(8)
        categorical_summary[col] = {
            "unique": int(df[col].nunique(dropna=True)),
            "top": {str(k): int(v) for k, v in vc.items()},
        }

    datetime_summary: Dict[str, Any] = {}
    for col in classes["datetime"]:
        s = pd.to_datetime(df[col], errors="coerce").dropna()
        if len(s) == 0:
            continue
        datetime_summary[col] = {
            "min": str(s.min().date()),
            "max": str(s.max().date()),
            "span_days": int((s.max() - s.min()).days),
        }

    return {
        "rows": int(len(df)),
        "columns": int(len(df.columns)),
        "column_names": list(df.columns),
        "classes": classes,
        "numeric_summary": numeric_summary,
        "categorical_summary": categorical_summary,
        "datetime_summary": datetime_summary,
        "missing_per_column": {c: int(df[c].isna().sum()) for c in df.columns},
        "cleaning_applied": list(cleaning_report or []),
    }


# ============================================================================
# Public load API
# ============================================================================
def load_dataframe(session: SessionData, df: pd.DataFrame, dataset_name: str = "dataset") -> List[str]:
    """Cleans and indexes `df` into `session` (in place). Returns
    human-readable changes. Every session gets its own SQLite file
    (`session.db_path`), so concurrent sessions never share a table."""
    df, changes = clean_dataframe(df)
    session.df = df
    session.cleaning_report = changes
    session.dataset_name = dataset_name
    session.profile_cache = build_profile(df, cleaning_report=changes)

    df_sql = df.copy()
    for c in df_sql.columns:
        if pd.api.types.is_datetime64_any_dtype(df_sql[c]):
            df_sql[c] = df_sql[c].astype(str)

    conn = sqlite3.connect(session.db_path)
    df_sql.to_sql(session.table_name, conn, if_exists="replace", index=False)
    conn.close()

    return changes


# ============================================================================
# LangChain tools — bound to one session
# ============================================================================
def make_session_tools(session: SessionData) -> list:
    """Build a fresh set of LangChain tools bound to `session` via closure.
    Each session gets its own tool instances, so the agent can never read or
    query another session's dataframe or SQLite table."""

    @tool
    def profile_data(input: str = "") -> str:
        """Profile the loaded dataset. Returns JSON with columns, types
        (numeric/categorical/datetime/text/id), summary stats, top categories,
        missing-value counts, and cleaning applied. Always call this FIRST."""
        if session.df is None:
            return "No data loaded yet."
        return json.dumps(build_profile(session.df, session.cleaning_report), indent=2, default=str)

    @tool
    def get_schema(input: str = "") -> str:
        """Lightweight schema view: column name, type, one example value.
        Use this before writing SQL."""
        if session.df is None:
            return "No data loaded yet."
        lines = [f"Table: {session.table_name}", "Columns:"]
        for col, dtype in session.df.dtypes.items():
            sample = session.df[col].dropna().iloc[0] if session.df[col].notna().any() else "N/A"
            sample_str = str(sample)
            if len(sample_str) > 40:
                sample_str = sample_str[:37] + "..."
            lines.append(f"  - {col} ({dtype}) example: {sample_str}")
        return "\n".join(lines)

    @tool
    def run_sql(query: str) -> str:
        """Run a read-only SQL SELECT against the loaded dataset. Table is 'data'.
        Returns at most 25 rows. Always call get_schema first to learn the column
        names."""
        if session.df is None:
            return "No data loaded yet."
        q = (query or "").strip().rstrip(";")
        if not (q.upper().startswith("SELECT") or q.upper().startswith("WITH")):
            return "Only SELECT/WITH queries are allowed."
        try:
            conn = sqlite3.connect(session.db_path)
            result = pd.read_sql_query(q, conn)
            conn.close()
            if result.empty:
                return "Query returned 0 rows."
            return result.head(25).to_string(index=False)
        except Exception as e:
            return f"SQL Error: {e}"

    @tool
    def value_counts(column: str, top_n: int = 10) -> str:
        """Most common values for a categorical column and their counts.
        Use for 'most common X' or 'breakdown of X'."""
        if session.df is None:
            return "No data loaded yet."
        if column not in session.df.columns:
            return f"Column '{column}' not found. Available: {list(session.df.columns)}"
        vc = session.df[column].value_counts(dropna=True).head(top_n)
        return vc.to_string()

    @tool
    def top_n(group_by: str, metric: str, n: int = 5, ascending: bool = False) -> str:
        """Group by `group_by`, sum `metric`, return top (or bottom) N.
        ascending=True returns the bottom N. Use for 'top X by Y' questions."""
        if session.df is None:
            return "No data loaded yet."
        if group_by not in session.df.columns:
            return f"Group column '{group_by}' not found."
        if metric not in session.df.columns:
            return f"Metric column '{metric}' not found."
        s = pd.to_numeric(session.df[metric], errors="coerce")
        if s.isna().all():
            return f"Metric '{metric}' is not numeric."
        grouped = s.groupby(session.df[group_by]).sum().sort_values(ascending=ascending).head(n)
        return grouped.round(2).to_string()

    @tool
    def time_series(date_column: str, metric: str, freq: str = "ME") -> str:
        """Aggregate `metric` over time using `date_column`.
        freq: D=day, W=week, ME=month-end, QE=quarter, YE=year."""
        if session.df is None:
            return "No data loaded yet."
        if date_column not in session.df.columns:
            return f"Date column '{date_column}' not found."
        if metric not in session.df.columns:
            return f"Metric '{metric}' not found."
        dates = pd.to_datetime(session.df[date_column], errors="coerce")
        vals = pd.to_numeric(session.df[metric], errors="coerce")
        df_t = pd.DataFrame({"d": dates, "v": vals}).dropna()
        if df_t.empty:
            return "No valid date+metric pairs."
        # Map old pandas freq aliases to new ones
        freq_map = {"Q": "QE", "M": "ME", "A": "YE", "Y": "YE"}
        freq = freq_map.get(freq.upper(), freq)
        grouped = df_t.set_index("d")["v"].resample(freq).sum()
        return grouped.round(2).to_string()

    @tool
    def correlations(threshold: float = 0.5) -> str:
        """Pairs of numeric columns whose absolute correlation exceeds the threshold.
        Useful for finding relationships in unfamiliar datasets."""
        if session.df is None:
            return "No data loaded yet."
        num = session.df.select_dtypes(include=[np.number])
        if num.shape[1] < 2:
            return "Not enough numeric columns to correlate."
        corr = num.corr().round(3)
        pairs = []
        for i in range(len(corr.columns)):
            for j in range(i + 1, len(corr.columns)):
                v = corr.iloc[i, j]
                if pd.notna(v) and abs(v) >= threshold:
                    pairs.append((corr.columns[i], corr.columns[j], float(v)))
        pairs.sort(key=lambda x: -abs(x[2]))
        if not pairs:
            return f"No correlations above |{threshold}|."
        return "\n".join(f"{a} <-> {b}: {v:+.2f}" for a, b, v in pairs[:20])

    @tool
    def anomaly_detect(column: str) -> str:
        """Detect outliers in a numeric column using the IQR method (Q1 - 1.5×IQR, Q3 + 1.5×IQR).
        Use for 'anything unusual', 'outliers', 'spikes', 'what looks off'."""
        if session.df is None:
            return "No data loaded yet."
        if column not in session.df.columns:
            return f"Column '{column}' not found. Available: {list(session.df.columns)}"
        s = pd.to_numeric(session.df[column], errors="coerce").dropna()
        if s.empty:
            return f"Column '{column}' has no numeric values."
        q1, q3 = float(s.quantile(0.25)), float(s.quantile(0.75))
        iqr = q3 - q1
        lower, upper = q1 - 1.5 * iqr, q3 + 1.5 * iqr
        col_numeric = pd.to_numeric(session.df[column], errors="coerce")
        mask = col_numeric.lt(lower) | col_numeric.gt(upper)
        outliers = session.df[mask]
        count = int(len(outliers))
        if count == 0:
            return json.dumps({
                "column": column, "outlier_count": 0,
                "bounds": {"lower": round(lower, 4), "upper": round(upper, 4)},
                "message": "No outliers found.",
            })
        return json.dumps({
            "column": column,
            "outlier_count": count,
            "bounds": {"lower": round(lower, 4), "upper": round(upper, 4)},
            "outlier_rows": json.loads(
                outliers.head(20).to_json(orient="records", default_handler=str)
            ),
        }, indent=2, default=str)

    return [profile_data, get_schema, run_sql, value_counts, top_n, time_series, correlations, anomaly_detect]


# ============================================================================
# UI helper
# ============================================================================
def quick_prompts_for_dataset(session: SessionData) -> List[str]:
    """Generate dataset-aware quick prompts using the actual columns of `session`."""
    if session.df is None or session.profile_cache is None:
        return []
    classes = session.profile_cache["classes"]
    prompts: List[str] = ["Give me an overview of this dataset"]

    # Exclude ID columns from metric suggestions
    id_cols = set(classes.get("id", []))
    num_cols = [c for c in classes["numeric"] if c not in id_cols][:2]
    cat_cols = classes["categorical"][:2]
    date_cols = classes["datetime"][:1]

    if num_cols and cat_cols:
        prompts.append(f"Top {cat_cols[0]} by {num_cols[0]}")
    if num_cols:
        prompts.append(f"What's the distribution of {num_cols[0]}?")
    if date_cols and num_cols:
        prompts.append(f"How does {num_cols[0]} change over time?")
    if cat_cols:
        prompts.append(f"Breakdown of {cat_cols[0]}")
    if len(num_cols) >= 2:
        prompts.append(f"Is there a relationship between {num_cols[0]} and {num_cols[1]}?")
    prompts.append("What looks unusual or worth investigating?")
    return prompts[:6]
