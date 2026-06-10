import pandas as pd


def classify_column(s: pd.Series) -> str:
    """Classify a column's semantic type so the briefing layer
    only applies appropriate logic to it."""
    name = str(s.name).lower()
    n = len(s)
    nunique = s.nunique(dropna=True)

    if nunique <= 1:
        return "constant"

    if pd.api.types.is_datetime64_any_dtype(s):
        return "datetime"

    if pd.api.types.is_numeric_dtype(s):
        # ID detection: near-all-unique numeric, or id-like name
        id_words = ["id", "number", "code", "key", "index"]
        if nunique >= 0.95 * n:
            return "id"
        if any(w in name for w in id_words) and nunique >= 0.5 * n:
            return "id"
        # Rates/scores/levels: not additive
        rate_words = ["rate", "score", "level", "satisfaction",
                      "rating", "involvement", "balance", "percent",
                      "age", "distance", "hours"]
        if any(w in name for w in rate_words):
            return "rate_or_score"
        return "metric"

    # Non-numeric
    if nunique == 2:
        vals = set(str(v).strip().lower() for v in s.dropna().unique())
        if vals & {"yes", "no", "true", "false", "y", "n", "0", "1"}:
            return "binary_outcome"
    if nunique <= max(20, 0.05 * n):
        return "category"
    return "text"
