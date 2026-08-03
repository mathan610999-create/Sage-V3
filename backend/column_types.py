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
        # 1a. Name ends with "id" or equals "id" — catches repeating IDs like
        #     "Retailer ID" (6 unique values) regardless of uniqueness ratio.
        #     Checked before the metric-word list below: a column literally
        #     named "..._id" is an identifier even if it also contains a
        #     metric word (e.g. "sales_id").
        if name_stripped == "id" or name_stripped.endswith("id"):
            return "id"
        # 1b. Other id-like name words with moderate-to-high uniqueness
        id_words = ["code", "key", "index"]
        if any(w in name for w in id_words) and nunique >= 0.5 * n:
            return "id"
        # 1c. Label/location/identifier numbers — these tag a record (which
        #     room, which zip code, which gate) rather than measure it,
        #     regardless of how many distinct values repeat
        #     (e.g. "Room Number", "Zip Code", "Label")
        id_name_words = ["room", "number", "zip", "postal", "phone",
                         "floor", "seat", "gate", "bed", "ward", "label"]
        if any(w in name for w in id_name_words):
            return "id"

        # ── Metric protection: additive business columns skip rate/ordinal AND
        # the near-all-unique ID check further down. Checked before that ID
        # check on purpose — continuous money amounts (e.g. "Total Sales"
        # with cents) are very often ~100% unique across rows, which used to
        # trip the ID check and silently drop real metric columns from the
        # dashboard/briefing.
        if any(w in name for w in _METRIC_PROTECT_WORDS):
            return "metric"

        # ── Rate/score: not additive (name-based). Also checked before the
        # near-all-unique ID fallback below, for the same reason as metric
        # protection above — a continuous rating/score column (e.g.
        # "Satisfaction Score" with decimal values) is often ~100% unique
        # too, and a name match here is a stronger signal than raw
        # uniqueness.
        rate_words = ["rate", "score", "level", "satisfaction",
                      "rating", "involvement", "balance", "percent",
                      "age", "distance", "hours",
                      "price", "perunit", "per_unit", "unit"]
        if any(w in name for w in rate_words):
            return "rate_or_score"

        # 1d. Near-all-unique values, once the column has cleared every
        #     name-based check above
        if nunique >= 0.95 * n:
            return "id"

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
