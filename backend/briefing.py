"""
briefing.py — dataset-agnostic executive briefing

Pure function over a dataframe so it can be unit-tested without the
FastAPI session layer.
"""
from __future__ import annotations
import pandas as pd

from column_types import classify_column

# A category is framed as "dominant" only once it both (a) holds an outright
# majority of records and (b) is meaningfully larger than an even split would
# give it — so "Male" at 52% of a 2-value Gender column (even split = 50%)
# isn't misreported as "leading", but "MediCorp" at 60% of a 4-value
# Insurance Provider column (even split = 25%) is.
DOMINANCE_MIN_SHARE = 50       # % — must be an outright majority
DOMINANCE_VS_EVEN_SPLIT = 1.5  # x — and this many times the even-split share

# A period-over-period shift smaller than this is normal noise, not a
# trend worth flagging.
TREND_MATERIALITY = 10  # %


def build_briefing(df: pd.DataFrame) -> dict:
    col_types     = {c: classify_column(df[c]) for c in df.columns}
    metric_cols   = [c for c, t in col_types.items() if t == "metric"]
    rate_cols     = [c for c, t in col_types.items() if t == "rate_or_score"]
    category_cols = [c for c, t in col_types.items() if t == "category"]
    binary_cols   = [c for c, t in col_types.items() if t == "binary_outcome"]
    datetime_cols = [c for c, t in col_types.items() if t == "datetime"]
    corr_eligible = metric_cols + rate_cols  # valid pairs for action card

    findings = []
    noticed  = []
    risk        = ""
    opportunity = ""
    action      = ""

    # Confidence score
    completeness = (1 - df.isnull().mean().mean())
    confidence = min(96, int(55 + completeness * 30 + min(len(df)/1000, 10)))

    # Finding 1 — outliers in primary metric col only; skip entirely when count == 0
    # Risk is only ever framed around true "metric" columns (additive business
    # quantities) — never rates/scores or id-like columns.
    if metric_cols:
        col = next((c for c in metric_cols if any(k in c.lower() for k in ['sales','revenue','profit','amount'])), metric_cols[0])
        s = pd.to_numeric(df[col], errors="coerce").dropna()
        Q1, Q3 = s.quantile(0.25), s.quantile(0.75)
        IQR = Q3 - Q1
        outliers = s[(s < Q1 - 1.5*IQR) | (s > Q3 + 1.5*IQR)]
        col_label = col.replace("_", " ").title()
        if len(outliers) > 0:
            pct = len(outliers)/len(s)*100
            findings.append({
                "title": f"{pct:.1f}% outliers in {col_label}",
                "detail": f"{len(outliers):,} of {len(s):,} records sit outside the normal range (IQR method). Mean is {s.mean():,.0f} vs median {s.median():,.0f} — a {s.mean()/max(s.median(),1):.1f}x gap.",
                "type": "anomaly"
            })
            risk = f"High concentration risk — {pct:.0f}% of {col_label} records are statistical outliers. These records drive a disproportionate share of the totals."
        # Mean/median noticed: only when ratio diverges meaningfully
        median = s.median()
        if median != 0:
            ratio = s.mean() / abs(median)
            if ratio > 1.25 or ratio < 0.8:
                noticed.append(f"The mean {col_label} is {ratio:.1f}x the median — a skewed distribution that can distort averages.")

    # Finding 2 — category concentration (category only, not binary_outcome)
    # Only framed as a "dominance" finding once the top category clears
    # DOMINANCE_THRESHOLD; an even split is reported neutrally instead.
    if category_cols:
        col = category_cols[0]
        vc = df[col].value_counts(dropna=True)
        top_pct = vc.iloc[0]/len(df)*100
        even_share = 100 / len(vc)
        col_label = col.replace("_", " ").title()
        if top_pct >= DOMINANCE_MIN_SHARE and top_pct >= DOMINANCE_VS_EVEN_SPLIT * even_share:
            findings.append({
                "title": f"{vc.index[0]} leads {col_label} at {top_pct:.0f}%",
                "detail": f"The top {col_label} represents {top_pct:.0f}% of all records. The remaining {len(vc)-1} categories share {100-top_pct:.0f}%.",
                "type": "concentration"
            })
            noticed.append(f"{vc.index[0]} represents {top_pct:.0f}% of all {col_label} records.")
            # Opportunity is restricted to metric columns — it should describe
            # how a real business quantity behaves in the smallest segment,
            # not just that segment's share of records.
            if metric_cols:
                metric_col = metric_cols[0]
                smallest_cat = vc.index[-1]
                seg_vals = pd.to_numeric(df.loc[df[col] == smallest_cat, metric_col], errors="coerce")
                overall_vals = pd.to_numeric(df[metric_col], errors="coerce")
                seg_mean, overall_mean = seg_vals.mean(), overall_vals.mean()
                metric_label = metric_col.replace("_", " ").title()
                opportunity = (
                    f"{smallest_cat} is only {vc.iloc[-1]/len(df)*100:.1f}% of records but averages "
                    f"{seg_mean:,.0f} {metric_label} (overall avg {overall_mean:,.0f}) — "
                    f"a segment with room to grow."
                )
            else:
                noticed.append(f"{vc.index[-1]} is the smallest {col_label} segment at {vc.iloc[-1]/len(df)*100:.1f}% of records.")
        else:
            noticed.append(f"{col_label} is fairly evenly distributed across {len(vc)} categories — {vc.index[0]} is the largest at {top_pct:.0f}%.")

    # Binary outcome — neutral split, no loaded language
    if binary_cols:
        col = binary_cols[0]
        vc = df[col].value_counts(dropna=True)
        col_label = col.replace("_", " ").title()
        parts = [f"{int(v):,} {k} ({v/len(df)*100:.0f}%)" for k, v in vc.items()]
        noticed.append(f"{col_label}: {' / '.join(parts)}.")

    # Finding 3 — time trend (metric cols only), only when the shift is
    # material (>= TREND_MATERIALITY%) — small wobbles aren't a "trend".
    if datetime_cols and metric_cols:
        try:
            date_col = datetime_cols[0]
            metric = next((c for c in metric_cols if any(k in c.lower() for k in ['sales','revenue','profit'])), metric_cols[0])
            ts = df.copy()
            ts[date_col] = pd.to_datetime(ts[date_col], errors="coerce")
            ts = ts.dropna(subset=[date_col]).set_index(date_col)[metric].resample("ME").sum()
            if len(ts) >= 4:
                first_half = ts.iloc[:len(ts)//2].mean()
                second_half = ts.iloc[len(ts)//2:].mean()
                pct_change = (second_half - first_half)/max(first_half,1)*100
                if abs(pct_change) >= TREND_MATERIALITY:
                    direction = "up" if pct_change > 0 else "down"
                    metric_label = metric.replace("_", " ").title()
                    findings.append({
                        "title": f"{metric_label} trended {direction} {abs(pct_change):.0f}% over the period",
                        "detail": f"First half average: {first_half:,.0f}. Second half average: {second_half:,.0f}. The trend is {'positive' if pct_change > 0 else 'concerning'} and consistent.",
                        "type": "trend"
                    })
                    noticed.append(f"{metric_label} in the second half of the dataset is {abs(pct_change):.0f}% {'higher' if pct_change > 0 else 'lower'} than the first half — a structural shift worth investigating.")
                    action = f"Investigate what changed at the midpoint of the {date_col.replace('_',' ')} range — the {abs(pct_change):.0f}% shift suggests an external event or strategic change."
        except Exception:
            pass

    # Recommended action: only suggest correlations between metric/rate_or_score pairs
    if not action and len(corr_eligible) >= 2:
        action = f"Run a correlation analysis between {corr_eligible[0].replace('_',' ')} and {corr_eligible[1].replace('_',' ')} to identify key drivers."

    noticed.append(f"Dataset is {confidence}% complete with {len(df):,} rows and {len(df.columns)} columns — {'sufficient' if len(df) > 1000 else 'limited'} for reliable analysis.")

    return {
        "confidence": confidence,
        "rows": len(df),
        "cols": len(df.columns),
        "findings": findings[:3],
        "noticed": noticed[:5],
        "risk": risk,
        "opportunity": opportunity,
        "action": action,
        "executive_summary": f"Dataset contains {len(df):,} records across {len(df.columns)} fields. {findings[0]['title'] if findings else 'Initial analysis complete.'}",
    }
