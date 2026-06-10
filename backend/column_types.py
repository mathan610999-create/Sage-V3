import pandas as pd

# Additive business metric names — bypass rate/ordinal checks
_METRIC_PROTECT_WORDS = {"profit", "sales", "revenue", "income", "cost",
                         "amount", "spend", "units", "quantity"}


def classify_column(s: pd.Series) -> str:
    """Classify a column's semantic type so the briefing layer
    only applies appropriate logic to it."""
    name = str(s.name).lower()
    # Stripped name (no spaces/underscores) used for ID suffix check only
    name_stripped = name.replace(" ", "").replace("_", "")
    n = len(s)
    nunique = s.nunique(dropna=True)

    if nunique <= 1:
        return "constant"

    if pd.api.types.is_datetime64_any_dtype(s):
        return "datetime"

    if pd.api.types.is_numeric_dtype(s):
        # ── ID detection (highest priority, checked before everything else) ──
        # 1a. Near-all-unique values
        if nunique >= 0.95 * n:
            return "id"
        # 1b. Name ends with "id" or equals "id" — catches repeating IDs like
        #     "Retailer ID" (6 unique values) regardless of uniqueness ratio
        if name_stripped == "id" or name_stripped.endswith("id"):
            return "id"
        # 1c. Other id-like name words with moderate-to-high uniqueness
        id_words = ["number", "code", "key", "index"]
        if any(w in name for w in id_words) and nunique >= 0.5 * n:
            return "id"

        # ── Metric protection: additive business columns skip rate/ordinal checks ──
        if any(w in name for w in _METRIC_PROTECT_WORDS):
            return "metric"

        # ── Rate/score: not additive (name-based) ──
        rate_words = ["rate", "score", "level", "satisfaction",
                      "rating", "involvement", "balance", "percent",
                      "age", "distance", "hours",
                      "price", "perunit", "per_unit", "unit"]
        if any(w in name for w in rate_words):
            return "rate_or_score"

        # ── Ordinal/scale: small-range integers caught by value shape ──
        # Covers Education (1-5), JobLevel (1-5), StockOptionLevel (0-3),
        # NumCompaniesWorked (0-9), TrainingTimesLastYear, etc.
        if pd.api.types.is_integer_dtype(s) or (s.dropna() % 1 == 0).all():
            if nunique <= 10 and s.max() <= 10 and s.min() >= 0:
                return "rate_or_score"

        return "metric"

    # ── Non-numeric ──
    if nunique == 2:
        vals = set(str(v).strip().lower() for v in s.dropna().unique())
        if vals & {"yes", "no", "true", "false", "y", "n", "0", "1"}:
            return "binary_outcome"
    if nunique <= max(20, 0.05 * n):
        return "category"
    return "text"
