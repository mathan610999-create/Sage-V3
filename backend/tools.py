"""
tools.py - Sage data layer (dataset-agnostic)

Loads ANY CSV/Excel into SQLite + a pandas DataFrame, profiles columns
generically, exposes LangChain tools the agent uses to answer questions
about whatever the user uploaded. No hardcoded business columns.
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

# Module state
_df: Optional[pd.DataFrame] = None
_db_path: str = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sage_data.db")
_table_name: str = "data"
_cleaning_report: List[str] = []
_profile_cache: Optional[Dict[str, Any]] = None
_dataset_name: Optional[str] = None


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
        if df[col].dtype == object and _looks_numeric(df[col]):
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
        if df[col].dtype == object and _looks_datetime(df[col]):
            df[col] = pd.to_datetime(df[col], errors="coerce")
            parsed_dates.append(col)
    if parsed_dates:
        changes.append(f"Parsed {len(parsed_dates)} date column(s): " + ", ".join(parsed_dates))

    for col in df.select_dtypes(include=["object"]).columns:
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


def _looks_like_sequence(s: pd.Series) -> bool:
    """True if values are essentially a contiguous sequence (e.g. 1,2,3...)."""
    vals = pd.to_numeric(s, errors="coerce").dropna()
    if len(vals) < 20:
        return False
    diffs = vals.sort_values().diff().dropna()
    if diffs.empty:
        return False
    return float((diffs == diffs.mode().iloc[0]).mean()) > 0.9


def _classify_columns(df: pd.DataFrame) -> Dict[str, List[str]]:
    """Classify columns into numeric / categorical / datetime / text / id.

    A column is flagged as 'id' only when its NAME looks like an identifier
    (contains id/code/key/uuid/guid/sku) AND uniqueness is high, OR when its
    values form a near-perfect sequence. Random high-uniqueness numerics
    like Salary or Revenue stay as 'numeric'.
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
            is_sequence = pd.api.types.is_integer_dtype(s) and _looks_like_sequence(s)
            if (name_looks_id and unique_ratio > 0.9) or is_sequence:
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


def build_profile(df: pd.DataFrame) -> Dict[str, Any]:
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
        "cleaning_applied": list(_cleaning_report),
    }


# ============================================================================
# Public load / accessor API
# ============================================================================
def load_dataframe(df: pd.DataFrame, dataset_name: str = "dataset") -> List[str]:
    """Cleans and indexes the dataframe. Returns human-readable changes."""
    global _df, _cleaning_report, _profile_cache, _dataset_name

    df, changes = clean_dataframe(df)
    _df = df
    _cleaning_report = changes
    _dataset_name = dataset_name
    _profile_cache = build_profile(df)

    df_sql = df.copy()
    for c in df_sql.columns:
        if pd.api.types.is_datetime64_any_dtype(df_sql[c]):
            df_sql[c] = df_sql[c].astype(str)

    conn = sqlite3.connect(_db_path)
    df_sql.to_sql(_table_name, conn, if_exists="replace", index=False)
    conn.close()

    return changes


def get_df() -> Optional[pd.DataFrame]:
    return _df


def get_profile() -> Optional[Dict[str, Any]]:
    return _profile_cache


def get_dataset_name() -> Optional[str]:
    return _dataset_name


def get_cleaning_report() -> List[str]:
    return list(_cleaning_report)


# ============================================================================
# LangChain tools
# ============================================================================
@tool
def profile_data(input: str = "") -> str:
    """Profile the loaded dataset. Returns JSON with columns, types
    (numeric/categorical/datetime/text/id), summary stats, top categories,
    missing-value counts, and cleaning applied. Always call this FIRST."""
    if _df is None:
        return "No data loaded yet."
    return json.dumps(build_profile(_df), indent=2, default=str)


@tool
def get_schema(input: str = "") -> str:
    """Lightweight schema view: column name, type, one example value.
    Use this before writing SQL."""
    if _df is None:
        return "No data loaded yet."
    lines = [f"Table: {_table_name}", "Columns:"]
    for col, dtype in _df.dtypes.items():
        sample = _df[col].dropna().iloc[0] if _df[col].notna().any() else "N/A"
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
    if _df is None:
        return "No data loaded yet."
    q = (query or "").strip().rstrip(";")
    if not (q.upper().startswith("SELECT") or q.upper().startswith("WITH")):
        return "Only SELECT/WITH queries are allowed."
    try:
        conn = sqlite3.connect(_db_path)
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
    if _df is None:
        return "No data loaded yet."
    if column not in _df.columns:
        return f"Column '{column}' not found. Available: {list(_df.columns)}"
    vc = _df[column].value_counts(dropna=True).head(top_n)
    return vc.to_string()


@tool
def top_n(group_by: str, metric: str, n: int = 5, ascending: bool = False) -> str:
    """Group by `group_by`, sum `metric`, return top (or bottom) N.
    ascending=True returns the bottom N. Use for 'top X by Y' questions."""
    if _df is None:
        return "No data loaded yet."
    if group_by not in _df.columns:
        return f"Group column '{group_by}' not found."
    if metric not in _df.columns:
        return f"Metric column '{metric}' not found."
    s = pd.to_numeric(_df[metric], errors="coerce")
    if s.isna().all():
        return f"Metric '{metric}' is not numeric."
    grouped = s.groupby(_df[group_by]).sum().sort_values(ascending=ascending).head(n)
    return grouped.round(2).to_string()


@tool
def time_series(date_column: str, metric: str, freq: str = "ME") -> str:
    """Aggregate `metric` over time using `date_column`.
    freq: D=day, W=week, ME=month-end, QE=quarter, YE=year."""
    if _df is None:
        return "No data loaded yet."
    if date_column not in _df.columns:
        return f"Date column '{date_column}' not found."
    if metric not in _df.columns:
        return f"Metric '{metric}' not found."
    dates = pd.to_datetime(_df[date_column], errors="coerce")
    vals = pd.to_numeric(_df[metric], errors="coerce")
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
    if _df is None:
        return "No data loaded yet."
    num = _df.select_dtypes(include=[np.number])
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
    if _df is None:
        return "No data loaded yet."
    if column not in _df.columns:
        return f"Column '{column}' not found. Available: {list(_df.columns)}"
    s = pd.to_numeric(_df[column], errors="coerce").dropna()
    if s.empty:
        return f"Column '{column}' has no numeric values."
    q1, q3 = float(s.quantile(0.25)), float(s.quantile(0.75))
    iqr = q3 - q1
    lower, upper = q1 - 1.5 * iqr, q3 + 1.5 * iqr
    col_numeric = pd.to_numeric(_df[column], errors="coerce")
    mask = col_numeric.lt(lower) | col_numeric.gt(upper)
    outliers = _df[mask]
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


# ============================================================================
# UI helper
# ============================================================================
def quick_prompts_for_dataset() -> List[str]:
    """Generate dataset-aware quick prompts using the actual columns."""
    if _df is None or _profile_cache is None:
        return []
    classes = _profile_cache["classes"]
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