"""
report.py — PDF export and shareable read-only HTML report for a session.

Combines three things already computed elsewhere into one artifact:
  - the executive briefing (briefing.build_briefing)
  - the dashboard charts (the same shapes main.dashboard_data() returns)
  - the full chat Q&A history (store.get_messages)

Charts are rendered once as PNG images via matplotlib (Agg backend — no
display needed on a server) and reused by both outputs, so the PDF and the
shareable link never disagree with each other:
  - generate_report_pdf(...)  -> bytes (a downloadable PDF)
  - generate_report_html(...) -> str   (a self-contained HTML page used for
    the public "anyone with the link" share view)
"""
from __future__ import annotations

import base64
import io
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from reportlab.lib import colors
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Image as RLImage,
    PageBreak, HRFlowable,
)

_ACCENT = "#6b5b95"  # matches the frontend's sage/purple palette


def _fig_to_png_bytes(fig) -> bytes:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf.read()


def _chart_timeseries(ts: Dict[str, Any]) -> Optional[bytes]:
    data = (ts or {}).get("data") or []
    if not data:
        return None
    labels = [d["date"] for d in data]
    values = [d["value"] for d in data]
    fig, ax = plt.subplots(figsize=(6.5, 2.8))
    ax.plot(labels, values, color=_ACCENT, linewidth=2, marker="o", markersize=3)
    ax.set_title(ts.get("title", ""), fontsize=10)
    ax.tick_params(axis="x", rotation=45, labelsize=7)
    ax.tick_params(axis="y", labelsize=7)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    fig.tight_layout()
    return _fig_to_png_bytes(fig)


def _chart_bar(bar: Dict[str, Any]) -> Optional[bytes]:
    data = bar.get("data") or []
    if not data:
        return None
    names = [str(d["name"])[:18] for d in data]
    values = [d["value"] for d in data]
    fig, ax = plt.subplots(figsize=(5, 3))
    ax.barh(names[::-1], values[::-1], color=_ACCENT)
    ax.set_title(bar.get("title", ""), fontsize=10)
    ax.tick_params(labelsize=7)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    fig.tight_layout()
    return _fig_to_png_bytes(fig)


def _chart_donut(donut: Dict[str, Any]) -> Optional[bytes]:
    data = donut.get("data") or []
    if not data:
        return None
    labels = [str(d["name"])[:16] for d in data]
    values = [d["value"] for d in data]
    fig, ax = plt.subplots(figsize=(4, 4))
    palette = plt.cm.Purples([max(0.35, 0.9 - i * 0.12) for i in range(len(values))])
    ax.pie(values, labels=labels, autopct="%1.0f%%", colors=palette,
           wedgeprops=dict(width=0.45), textprops={"fontsize": 7})
    ax.set_title(donut.get("title", ""), fontsize=10)
    fig.tight_layout()
    return _fig_to_png_bytes(fig)


def _chart_histogram(hist: Dict[str, Any]) -> Optional[bytes]:
    data = hist.get("data") or []
    if not data:
        return None
    bins = [str(d["bin"]) for d in data]
    counts = [d["count"] for d in data]
    fig, ax = plt.subplots(figsize=(5, 2.8))
    ax.bar(bins, counts, color=_ACCENT, width=0.9)
    ax.set_title(hist.get("title", ""), fontsize=10)
    ax.tick_params(axis="x", rotation=90, labelsize=6)
    ax.tick_params(axis="y", labelsize=7)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    fig.tight_layout()
    return _fig_to_png_bytes(fig)


def render_all_charts(dash: Dict[str, Any]) -> Dict[str, bytes]:
    """Render every chart from a dashboard-data payload into PNG bytes,
    keyed so both the PDF and HTML builders can pull the same images."""
    out: Dict[str, bytes] = {}
    if dash.get("timeseries"):
        png = _chart_timeseries(dash["timeseries"])
        if png:
            out["timeseries"] = png
    for i, bar in enumerate(dash.get("bars", [])[:4]):
        png = _chart_bar(bar)
        if png:
            out[f"bar_{i}"] = png
    for i, donut in enumerate(dash.get("donuts", [])[:4]):
        png = _chart_donut(donut)
        if png:
            out[f"donut_{i}"] = png
    for i, hist in enumerate(dash.get("histograms", [])[:3]):
        png = _chart_histogram(hist)
        if png:
            out[f"hist_{i}"] = png
    return out


def _fmt_time(ts: Optional[float]) -> str:
    if not ts:
        return ""
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%b %d, %Y %H:%M UTC")


# ── PDF ──

def generate_report_pdf(
    session_meta: Dict[str, Any],
    briefing: Dict[str, Any],
    messages: List[Dict[str, Any]],
    chart_images: Dict[str, bytes],
) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=LETTER,
        topMargin=0.75 * inch, bottomMargin=0.75 * inch,
        leftMargin=0.75 * inch, rightMargin=0.75 * inch,
    )
    styles = getSampleStyleSheet()
    h1 = ParagraphStyle("h1", parent=styles["Heading1"], textColor=colors.HexColor(_ACCENT), fontSize=20, spaceAfter=4)
    h2 = ParagraphStyle("h2", parent=styles["Heading2"], textColor=colors.HexColor(_ACCENT), fontSize=13, spaceBefore=14, spaceAfter=6)
    meta_style = ParagraphStyle("meta", parent=styles["Normal"], textColor=colors.grey, fontSize=9)
    body = styles["Normal"]
    bold = ParagraphStyle("bold", parent=styles["Normal"], fontName="Helvetica-Bold")

    story = []
    story.append(Paragraph("Sage Analysis Report", h1))
    story.append(Paragraph(
        f"{session_meta.get('filename', 'Dataset')} &middot; "
        f"{session_meta.get('rows', 0):,} rows &middot; {session_meta.get('cols', 0)} columns &middot; "
        f"generated {_fmt_time(session_meta.get('uploaded_at'))}",
        meta_style,
    ))
    story.append(HRFlowable(width="100%", color=colors.HexColor(_ACCENT), thickness=1, spaceBefore=8, spaceAfter=12))

    story.append(Paragraph("Executive Briefing", h2))
    story.append(Paragraph(f"Confidence: {briefing.get('confidence', 0)}%", bold))
    story.append(Paragraph(briefing.get("executive_summary", ""), body))
    story.append(Spacer(1, 8))

    if briefing.get("risk"):
        story.append(Paragraph("Risk", bold))
        story.append(Paragraph(briefing["risk"], body))
        story.append(Spacer(1, 6))
    if briefing.get("opportunity"):
        story.append(Paragraph("Opportunity", bold))
        story.append(Paragraph(briefing["opportunity"], body))
        story.append(Spacer(1, 6))
    if briefing.get("action"):
        story.append(Paragraph("Recommended Action", bold))
        story.append(Paragraph(briefing["action"], body))
        story.append(Spacer(1, 6))

    if briefing.get("findings"):
        story.append(Paragraph("Key Findings", bold))
        for f in briefing["findings"]:
            story.append(Paragraph(f"&bull; <b>{f['title']}</b> &mdash; {f['detail']}", body))
        story.append(Spacer(1, 6))

    if briefing.get("noticed"):
        story.append(Paragraph("Also Noticed", bold))
        for n in briefing["noticed"]:
            story.append(Paragraph(f"&bull; {n}", body))

    if chart_images:
        story.append(PageBreak())
        story.append(Paragraph("Dashboard", h2))
        for png in chart_images.values():
            img = RLImage(io.BytesIO(png), width=5.5 * inch, height=5.5 * inch * 0.55)
            img.hAlign = "CENTER"
            story.append(img)
            story.append(Spacer(1, 10))

    if messages:
        story.append(PageBreak())
        story.append(Paragraph("Conversation History", h2))
        for m in messages:
            label = "You" if m["role"] == "user" else "Sage"
            content = (m.get("content") or "").replace("\n", "<br/>")
            story.append(Paragraph(f"<b>{label}:</b> {content}", body))
            story.append(Spacer(1, 8))

    doc.build(story)
    buf.seek(0)
    return buf.read()


# ── Shareable HTML ──

def _esc(s: Optional[str]) -> str:
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def generate_report_html(
    session_meta: Dict[str, Any],
    briefing: Dict[str, Any],
    messages: List[Dict[str, Any]],
    chart_images: Dict[str, bytes],
) -> str:
    imgs_html = "".join(
        f'<img src="data:image/png;base64,{base64.b64encode(png).decode()}" '
        f'style="width:100%;max-width:640px;border-radius:12px;margin:12px 0;display:block;" />'
        for png in chart_images.values()
    )

    findings_html = "".join(
        f'<div class="finding"><b>{_esc(f["title"])}</b><p>{_esc(f["detail"])}</p></div>'
        for f in briefing.get("findings", [])
    )
    noticed_html = "".join(f"<li>{_esc(n)}</li>" for n in briefing.get("noticed", []))

    chat_html = "".join(
        f'<div class="msg {m["role"]}"><span class="who">{"You" if m["role"] == "user" else "Sage"}</span>'
        f'<div class="bubble">{_esc(m.get("content", ""))}</div></div>'
        for m in messages
    )

    risk_html = f'<p><b>Risk:</b> {_esc(briefing["risk"])}</p>' if briefing.get("risk") else ""
    opp_html = f'<p><b>Opportunity:</b> {_esc(briefing["opportunity"])}</p>' if briefing.get("opportunity") else ""
    action_html = f'<p><b>Recommended action:</b> {_esc(briefing["action"])}</p>' if briefing.get("action") else ""

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<title>Sage Report — {_esc(session_meta.get('filename', ''))}</title>
<meta name="viewport" content="width=device-width, initial-scale=1" />
<style>
  * {{ box-sizing: border-box; }}
  body {{ font-family: -apple-system, Inter, "Segoe UI", sans-serif; background:#faf9fc; color:#2d2a3a; margin:0; padding:0 16px 60px; }}
  .wrap {{ max-width: 720px; margin: 0 auto; }}
  header {{ padding: 40px 0 20px; }}
  h1 {{ font-size: 26px; margin: 0 0 6px; color:#4a3f6b; }}
  .meta {{ color:#8a83a3; font-size: 13px; }}
  h2 {{ font-size: 16px; color:#6b5b95; margin: 32px 0 12px; border-bottom: 1px solid #e6e1f2; padding-bottom: 8px; }}
  .card {{ background:#fff; border:1px solid #ece7f7; border-radius:14px; padding:18px 20px; margin-bottom:14px; }}
  .card p {{ margin: 6px 0; font-size: 14px; }}
  .finding p {{ margin: 4px 0 0; color:#5b5473; font-size: 14px; }}
  ul {{ padding-left: 18px; color:#5b5473; font-size: 14px; }}
  .msg {{ margin-bottom: 12px; }}
  .who {{ font-size: 11px; text-transform: uppercase; letter-spacing: .04em; color:#a89fc4; display:block; margin-bottom:2px; }}
  .bubble {{ background:#fff; border:1px solid #ece7f7; border-radius:12px; padding:10px 14px; font-size: 14px; white-space: pre-wrap; }}
  .msg.user .bubble {{ background:#f1edfb; }}
  footer {{ text-align:center; color:#b3acc9; font-size:12px; padding: 40px 0; }}
</style>
</head>
<body>
<div class="wrap">
  <header>
    <h1>Sage Analysis Report</h1>
    <div class="meta">{_esc(session_meta.get('filename', ''))} &middot; {session_meta.get('rows', 0):,} rows &middot; {session_meta.get('cols', 0)} columns</div>
  </header>

  <h2>Executive Briefing</h2>
  <div class="card">
    <p><b>Confidence:</b> {briefing.get('confidence', 0)}%</p>
    <p>{_esc(briefing.get('executive_summary', ''))}</p>
    {risk_html}{opp_html}{action_html}
  </div>
  {f'<div class="card">{findings_html}</div>' if findings_html else ''}
  {f'<div class="card"><ul>{noticed_html}</ul></div>' if noticed_html else ''}

  {'<h2>Dashboard</h2>' if imgs_html else ''}
  {imgs_html}

  {'<h2>Conversation History</h2>' if chat_html else ''}
  {chat_html}

  <footer>Generated by Sage</footer>
</div>
</body>
</html>"""
