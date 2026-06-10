"""
main.py — Sage FastAPI backend
"""
from __future__ import annotations
import asyncio
import json
import os
import uuid
import sqlite3
import tempfile
from pathlib import Path
from typing import Optional

import pandas as pd
from fastapi import FastAPI, UploadFile, File, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

from tools import load_dataframe, get_df, build_profile
from agent import build_agent, run_agent_with_trace

app = FastAPI(title="Sage API", version="3.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory session store
sessions: dict = {}

# ── Models ──
class AskRequest(BaseModel):
    question: str
    session_id: Optional[str] = None

class AskResponse(BaseModel):
    answer: str
    session_id: str
    tools_called: list
    sql_used: Optional[str] = None

# ── Health ──
@app.get("/")
def health():
    return {"status": "ok", "product": "Sage", "version": "3.0.0"}

# ── Upload dataset ──
@app.post("/upload")
async def upload_dataset(file: UploadFile = File(...)):
    try:
        session_id = str(uuid.uuid4())
        contents = await file.read()
        suffix = Path(file.filename).suffix.lower()

        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(contents)
            tmp_path = tmp.name

        if suffix == ".csv":
            df = pd.read_csv(tmp_path)
        elif suffix in [".xlsx", ".xls"]:
            from tools import smart_read_excel
            with open(tmp_path, "rb") as f:
                df = smart_read_excel(f)
        else:
            raise HTTPException(400, "Unsupported file type. Use CSV or Excel.")

        changes = load_dataframe(df, dataset_name=file.filename)
        profile = build_profile(df)
        agent = build_agent()
        sessions[session_id] = {
            "agent": agent,
            "filename": file.filename,
            "rows": len(df),
            "cols": len(df.columns),
            "columns": list(df.columns),
            "profile": profile,
        }
        os.unlink(tmp_path)

        return {
            "session_id": session_id,
            "filename": file.filename,
            "rows": len(df),
            "cols": len(df.columns),
            "columns": list(df.columns),
            "profile": profile,
            "changes": changes,
        }
    except Exception as e:
        raise HTTPException(500, str(e))

# ── Ask question ──
@app.post("/ask")
async def ask(req: AskRequest):
    try:
        session_id = req.session_id or str(uuid.uuid4())
        result = await asyncio.to_thread(run_agent_with_trace, req.question)
        return {
            "answer": result["content"],
            "session_id": session_id,
            "tools_called": [t["tool"] for t in result.get("trace", [])],
            "trace": result.get("trace", []),
        }
    except Exception as e:
        raise HTTPException(500, str(e))

# ── Speak text ──
class SpeakRequest(BaseModel):
    text: str

@app.post("/speak")
async def speak_text(req: SpeakRequest):
    try:
        from voice import speak
        audio_b64 = await asyncio.to_thread(speak, req.text)
        if not audio_b64:
            raise HTTPException(500, "TTS returned no audio")
        return {"audio": audio_b64}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))

# ── Transcribe audio ──
@app.post("/transcribe")
async def transcribe(file: UploadFile = File(...)):
    try:
        from voice import transcribe_audio
        audio_bytes = await file.read()
        transcript = transcribe_audio(audio_bytes)
        return {"transcript": transcript}
    except Exception as e:
        raise HTTPException(500, str(e))

# ── Dashboard data ──
@app.get("/dashboard/{session_id}")
def dashboard(session_id: str):
    session = sessions.get(session_id)
    if not session:
        raise HTTPException(404, "Session not found")
    return {
        "filename": session["filename"],
        "rows": session["rows"],
        "cols": session["cols"],
        "columns": session["columns"],
        "profile": session["profile"],
    }

# ── Currency column detection ($ prefix only for money-like names) ──
_CURRENCY_WORDS = {"price", "revenue", "sales", "income", "salary",
                   "cost", "amount", "spend", "pay"}

def _is_currency_col(col: str) -> bool:
    name = col.lower()
    return any(w in name for w in _CURRENCY_WORDS)

def _fmt_total(total: float, col: str) -> str:
    currency = _is_currency_col(col)
    prefix = "$" if currency else ""
    if total > 1_000_000:
        return f"{prefix}{total/1_000_000:.1f}M"
    if total > 1_000:
        return f"{prefix}{total/1_000:.1f}K"
    return f"{prefix}{total:.1f}"

# ── Dashboard computed data ──
@app.get("/dashboard-data/{session_id}")
def dashboard_data(session_id: str):
    try:
        df = get_df()
        if df is None:
            raise HTTPException(404, "No data loaded")

        from column_types import classify_column
        col_types = {c: classify_column(df[c]) for c in df.columns}

        metric_cols   = [c for c, t in col_types.items() if t == "metric"]
        rate_cols     = [c for c, t in col_types.items() if t == "rate_or_score"]
        category_cols = [c for c, t in col_types.items() if t in ("category", "binary_outcome")]
        datetime_cols = [c for c, t in col_types.items() if t == "datetime"]

        result = {}

        # 1. KPIs — total for metric ($ only for currency cols), average for rate_or_score
        kpis = [{"label": "Rows", "value": f"{len(df):,}", "sub": f"{len(df.columns)} columns"}]
        for col in metric_cols[:3]:
            s = pd.to_numeric(df[col], errors="coerce").dropna()
            total = s.sum()
            avg = s.mean()
            label = col.replace("_", " ").title()
            kpis.append({"label": f"Total {label}", "value": _fmt_total(total, col), "sub": f"avg {avg:,.0f}"})
        for col in rate_cols[:2]:
            s = pd.to_numeric(df[col], errors="coerce").dropna()
            avg = s.mean()
            label = col.replace("_", " ").title()
            kpis.append({"label": f"Avg {label}", "value": f"{avg:.1f}", "sub": f"{len(s):,} records"})
        result["kpis"] = kpis[:5]

        # 2. Time series — metric cols only (rate_or_score not summed over time)
        if datetime_cols and metric_cols:
            date_col = datetime_cols[0]
            preferred = ["total_sales", "revenue", "sales", "total_revenue", "amount", "value"]
            metric = next((c for c in metric_cols if c.lower() in preferred), metric_cols[0])
            try:
                ts = df.copy()
                ts[date_col] = pd.to_datetime(ts[date_col], errors="coerce")
                ts = ts.dropna(subset=[date_col])
                ts = ts.set_index(date_col)[metric].resample("ME").sum().reset_index()
                ts.columns = ["date", "value"]
                ts["date"] = ts["date"].dt.strftime("%b %Y")
                result["timeseries"] = {
                    "title": f"{metric.replace('_',' ').title()} over time",
                    "data": ts.tail(24).to_dict("records")
                }
            except Exception:
                pass

        # 3. Donut charts — category + binary_outcome cols; id/constant excluded
        donuts = []
        for col in category_cols[:4]:
            vc = df[col].value_counts(dropna=True).head(6).reset_index()
            vc.columns = ["name", "value"]
            donuts.append({
                "title": f"{col.replace('_',' ').title()} breakdown",
                "data": vc.to_dict("records")
            })
        result["donuts"] = donuts

        # 4. Histograms — metric + rate_or_score cols; id/constant excluded
        histograms = []
        for col in (metric_cols + rate_cols)[:3]:
            s = pd.to_numeric(df[col], errors="coerce").dropna()
            counts, bins = pd.cut(s, bins=20, retbins=True)
            hist_data = counts.value_counts(sort=False).reset_index()
            hist_data.columns = ["bin", "count"]
            hist_data["bin"] = hist_data["bin"].apply(lambda x: f"{x.left:.0f}")
            histograms.append({
                "title": f"{col.replace('_',' ').title()} distribution",
                "data": hist_data.to_dict("records")
            })
        result["histograms"] = histograms

        # 5. Bar charts — SUM for metric, MEAN for rate_or_score
        bars = []
        pure_category_cols = [c for c, t in col_types.items() if t == "category"]
        for cat_col in pure_category_cols[:2]:
            for num_col in metric_cols[:1]:
                grp = df.groupby(cat_col)[num_col].sum().sort_values(ascending=False).head(6).reset_index()
                grp.columns = ["name", "value"]
                bars.append({
                    "title": f"Top {cat_col.replace('_',' ')} by {num_col.replace('_',' ')}",
                    "data": grp.to_dict("records")
                })
            for num_col in rate_cols[:1]:
                grp = df.groupby(cat_col)[num_col].mean().sort_values(ascending=False).head(6).reset_index()
                grp.columns = ["name", "value"]
                bars.append({
                    "title": f"Avg {num_col.replace('_',' ').title()} by {cat_col.replace('_',' ').title()}",
                    "data": grp.round(2).to_dict("records")
                })
        result["bars"] = bars

        return result
    except Exception as e:
        raise HTTPException(500, str(e))

# ── Briefing ──
@app.get("/briefing/{session_id}")
def get_briefing(session_id: str):
    try:
        df = get_df()
        if df is None:
            raise HTTPException(404, "No data loaded")

        from briefing import build_briefing
        return build_briefing(df)
    except Exception as e:
        raise HTTPException(500, str(e))

# ── Voice WebSocket ──
@app.websocket("/voice")
async def voice_ws(websocket: WebSocket):
    await websocket.accept()
    try:
        from voice import transcribe_audio, speak, speak_thinking
        import base64
        while True:
            data = await websocket.receive_json()
            if data["type"] == "audio":
                audio_bytes = base64.b64decode(data["audio"])
                # Send thinking phrase immediately
                thinking_b64 = speak_thinking()
                if thinking_b64:
                    await websocket.send_json({
                        "type": "thinking_audio",
                        "audio": thinking_b64
                    })
                # Transcribe
                transcript = transcribe_audio(audio_bytes)
                await websocket.send_json({
                    "type": "transcript",
                    "text": transcript
                })
                # Run agent
                result = run_agent_with_trace(transcript)
                # Speak answer
                answer_b64 = speak(result["content"][:500])
                await websocket.send_json({
                    "type": "answer",
                    "text": result["content"],
                    "audio": answer_b64,
                    "tools_called": [t["tool"] for t in result.get("trace", [])],
                })
    except WebSocketDisconnect:
        pass
    except Exception as e:
        await websocket.send_json({"type": "error", "message": str(e)})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
