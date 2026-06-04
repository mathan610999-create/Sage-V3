"""
agent.py — Sage AI agent (dataset-agnostic)

A ReAct-style LangGraph agent with generic tools that work on any dataset.
The system prompt is deliberately domain-neutral and instructs the agent
to ground every answer in tool calls.
"""

from __future__ import annotations

import os
from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import MemorySaver

from tools import (
    profile_data,
    get_schema,
    run_sql,
    value_counts,
    top_n,
    time_series,
    correlations,
    anomaly_detect,
)

load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

SYSTEM_PROMPT = """You are Sage — a senior data analyst embedded directly inside the user's dataset.

You think like a McKinsey analyst, communicate like a trusted advisor, and always back every claim with real numbers from the data. The user may not be technical — your job is to surface insights they wouldn't have found on their own, explain what the numbers mean in plain language, and tell them exactly what to do next.

The dataset could be anything: sales, HR, finance, inventory, gaming, healthcare, surveys, sensor data. You adapt completely to whatever domain you're looking at.

═══════════════════════════════
WORKFLOW — always follow this
═══════════════════════════════

Step 1 — Profile first (once per session)
  On the first question, ALWAYS call `profile_data` before anything else.
  Use the result to understand column names, types, ranges, and cardinality.

Step 2 — Pick the right tool
  • `value_counts`  → distribution / "most common" / "breakdown of X"
  • `top_n`         → "top / bottom N items by metric", rankings
  • `time_series`   → trends, seasonality, month-over-month changes
  • `correlations`  → "what drives X", "what relates to X"
  • `anomaly_detect` → "anything unusual", "outliers", "spikes", "what looks off"
  • `run_sql`       → custom filters, comparisons, multi-column logic
    (always call `get_schema` immediately before any SQL)

Step 3 — Never stop at one tool
  Dig deeper. If `top_n` shows Action games outsell others, follow up with
  `time_series` to check if that lead is growing or shrinking.
  Chain 2–3 tool calls to give a genuinely useful answer.

═══════════════════════════════
RESPONSE STRUCTURE — always use this exact format
═══════════════════════════════

**🔍 The Key Finding**
One bold sentence. Lead with the most surprising or important thing you found.
State the exact number. E.g.: "Action games drive 34% of all global sales —
nearly 3× the next genre (Shooter at 12%)."

**📊 What the data shows**
2–4 sharp bullet points. Each must cite a real number from a tool result.
- Focus on the largest gaps, biggest outliers, and unexpected patterns.
- Compare: "X is 2.4× higher than the average" beats "X is high."
- Call out anything that looks like a problem or a hidden opportunity.

**⚡ What this means for you**
Translate the numbers into plain-English consequences.
- If sales are concentrated in one segment: "You're heavily exposed to one bet."
- If a trend is declining: "This has been falling for 3 consecutive periods —
  at this rate it will be X by next quarter."
- If an outlier is positive: "This is your biggest lever."

**🎯 Recommended next moves**
2–3 concrete, prioritised actions based strictly on what the data shows.
Frame as options: "One move worth considering is...", "The data suggests focusing on..."
Never invent data. If you don't have enough to recommend, say so and ask.

**💬 One question back**
End with exactly one sharp follow-up question that will unlock the next layer of insight.
Make it specific to this dataset's actual columns and values.

═══════════════════════════════
TONE & STYLE
═══════════════════════════════

- Write like a trusted senior analyst, not a chatbot.
- Be direct. If something is bad, say it's bad. If something is a clear win, say so.
- Never say "great question!" or other filler. Start with the insight.
- Use bold for numbers that matter: **$2.4M**, **Action**, **34%**
- Do NOT use * or ** inside numbers or inline values. Use plain text for all figures.
- Keep it scannable — use the section headers above every time.
- The user's time is precious. Every sentence must earn its place.

═══════════════════════════════
WHAT NOT TO DO
═══════════════════════════════

- Never invent column names, numbers, or metrics.
- Never skip tool calls — ground everything in real data.
- Never give generic advice that isn't specific to this dataset.
- Never write a wall of text — use the structure above.
- If data is missing or ambiguous, say so clearly and offer the closest available answer.

FORMATTING RULES: Never use ** or * for bold or italic. Never use # for headers. Write in plain text only. Use plain numbers and words — no markdown symbols of any kind.
"""


def build_agent():
    api_key = None
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    try:
        # utf-8-sig strips the BOM that Windows editors (Notepad etc.) add
        with open(env_path, encoding="utf-8-sig") as f:
            for line in f:
                line = line.strip()
                if line.startswith("#") or "=" not in line:
                    continue
                key, _, val = line.partition("=")
                if key.strip() == "ANTHROPIC_API_KEY":
                    # strip surrounding whitespace and optional quotes
                    api_key = val.strip().strip('"').strip("'")
                    break
    except Exception:
        pass

    if not api_key:
        api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError(f"ANTHROPIC_API_KEY missing. Looked in {env_path} and env.")

    llm = ChatAnthropic(
        model="claude-sonnet-4-6",
        temperature=0.2,
        api_key=api_key,
    )

    return create_react_agent(
        model=llm,
        tools=[
            profile_data,
            get_schema,
            run_sql,
            value_counts,
            top_n,
            time_series,
            correlations,
            anomaly_detect,
        ],
        prompt=SYSTEM_PROMPT,
        checkpointer=MemorySaver(),
    )


def _content_to_str(content) -> str:
    """Convert message content to string."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict):
                parts.append(block.get("text", ""))
            elif hasattr(block, "text"):
                parts.append(block.text)
        return " ".join(p for p in parts if p)
    return str(content) if content else ""


# Global agent instance and thread id
_agent = None
_thread_id = "default"


def get_or_build_agent():
    global _agent
    if _agent is None:
        _agent = build_agent()
    return _agent


def set_thread_id(thread_id: str):
    global _thread_id
    _thread_id = thread_id


def run_agent_with_trace(question: str) -> dict:
    """
    Invoke the agent and return:
    { content: str, trace: [{tool, args, result}] }
    """
    try:
        agent = get_or_build_agent()
        config = {"configurable": {"thread_id": _thread_id}}
        result = agent.invoke(
            {"messages": [{"role": "user", "content": question}]},
            config=config,
        )
    except Exception as e:
        return {"content": f"Error: {e}", "trace": []}

    msgs = result.get("messages", [])
    trace = []
    final_text = ""
    pending_tool_calls = {}

    for msg in msgs:
        tcs = getattr(msg, "tool_calls", None) or []
        if tcs:
            for tc in tcs:
                tc_id = tc.get("id") if isinstance(tc, dict) else getattr(tc, "id", None)
                tc_name = tc.get("name") if isinstance(tc, dict) else getattr(tc, "name", None)
                tc_args = tc.get("args") if isinstance(tc, dict) else getattr(tc, "args", {})
                if tc_id:
                    pending_tool_calls[tc_id] = {"name": tc_name, "args": tc_args or {}}
        if msg.__class__.__name__ == "ToolMessage":
            tc_id = getattr(msg, "tool_call_id", None)
            content = _content_to_str(msg.content)
            meta = pending_tool_calls.get(tc_id, {"name": getattr(msg, "name", "tool"), "args": {}})
            trace.append({
                "tool": meta["name"],
                "args": meta["args"],
                "result": content[:800],
            })

    for msg in reversed(msgs):
        content = _content_to_str(getattr(msg, "content", ""))
        if content and not getattr(msg, "tool_calls", None):
            final_text = content
            break

    if not final_text and msgs:
        final_text = _content_to_str(getattr(msgs[-1], "content", ""))

    return {"content": final_text, "trace": trace}
