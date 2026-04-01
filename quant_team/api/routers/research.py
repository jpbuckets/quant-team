"""Research Q&A API — ask the trading team questions without executing trades."""

from __future__ import annotations

import asyncio
import io
import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
from fpdf import FPDF

from ...teams.registry import TeamRegistry
from ...research import ResearchSession
from ..schemas import ResearchRequest

logger = logging.getLogger("quant_team")

router = APIRouter(prefix="/api/research", tags=["research"])

_sessions: dict[str, dict] = {}


def _update_progress(session_id: str, step: str, step_num: int, total_steps: int) -> None:
    if session_id in _sessions:
        _sessions[session_id]["progress"] = {
            "step": step,
            "step_num": step_num,
            "total_steps": total_steps,
        }
    logger.info(f"Research progress [{step_num}/{total_steps}]: {step}")


async def _run_research(session_id: str, question: str, team_id: str) -> None:
    _sessions[session_id] = {
        "generating": True,
        "error": None,
        "result": None,
        "progress": {"step": "Starting...", "step_num": 0, "total_steps": 6},
    }
    try:
        registry = TeamRegistry()
        config = registry.get(team_id)
        session = ResearchSession(config=config)
        result = await session.run(
            question=question,
            on_progress=lambda s, n, t: _update_progress(session_id, s, n, t),
        )
        _sessions[session_id]["result"] = result
        _sessions[session_id]["progress"] = {
            "step": "Complete",
            "step_num": _sessions[session_id]["progress"]["total_steps"],
            "total_steps": _sessions[session_id]["progress"]["total_steps"],
        }
        logger.info("Research session completed successfully")
    except asyncio.TimeoutError:
        _sessions[session_id]["error"] = "Research timed out after 5 minutes"
    except Exception as e:
        _sessions[session_id]["error"] = str(e)
        logger.error(f"Research session failed: {e}", exc_info=True)
    finally:
        _sessions[session_id]["generating"] = False


@router.post("/ask")
async def ask_question(body: ResearchRequest, background_tasks: BackgroundTasks):
    if any(s["generating"] for s in _sessions.values()):
        raise HTTPException(status_code=409, detail="Research session already in progress")
    session_id = str(uuid.uuid4())
    background_tasks.add_task(_run_research, session_id, body.question, body.team_id)
    return {"status": "started", "session_id": session_id}


@router.get("/status")
def research_status():
    if not _sessions:
        return {
            "generating": False,
            "error": None,
            "result": None,
            "progress": {"step": "", "step_num": 0, "total_steps": 6},
        }
    latest_id = list(_sessions.keys())[-1]
    s = _sessions[latest_id]
    return {
        "generating": s["generating"],
        "error": s["error"],
        "result": s["result"],
        "progress": s["progress"],
        "session_id": latest_id,
    }


_UNICODE_MAP = str.maketrans({
    "\u2018": "'", "\u2019": "'", "\u201c": '"', "\u201d": '"',
    "\u2013": "-", "\u2014": "--", "\u2022": "*", "\u2026": "...",
    "\u2032": "'", "\u2033": '"', "\u00a0": " ", "\u200b": "",
    "\u2010": "-", "\u2011": "-", "\u2012": "-",
})


def _sanitize(text: str) -> str:
    """Replace Unicode characters unsupported by PDF built-in fonts."""
    return text.translate(_UNICODE_MAP).encode("latin-1", errors="replace").decode("latin-1")


def _build_research_pdf(result: dict) -> bytes:
    """Build a formatted PDF from research session results."""
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=20)
    pdf.add_page()

    # --- Title ---
    pdf.set_font("Helvetica", "B", 20)
    pdf.set_text_color(0, 80, 40)
    pdf.cell(0, 12, "Quant Team Research Report", new_x="LMARGIN", new_y="NEXT")
    pdf.set_draw_color(0, 180, 80)
    pdf.set_line_width(0.6)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(4)

    # --- Metadata ---
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(100, 100, 100)
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    pdf.cell(0, 5, f"Generated: {timestamp}", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)

    # --- Question ---
    question = result.get("question", "")
    if question:
        pdf.set_font("Helvetica", "B", 11)
        pdf.set_text_color(40, 40, 40)
        pdf.cell(0, 7, "Research Question", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "I", 10)
        pdf.set_text_color(60, 60, 60)
        pdf.multi_cell(0, 5, _sanitize(question))
        pdf.ln(4)

    # --- Tickers ---
    tickers = result.get("tickers_analyzed", [])
    if tickers:
        pdf.set_font("Helvetica", "B", 9)
        pdf.set_text_color(0, 120, 60)
        pdf.cell(0, 6, f"Tickers Analyzed:  {', '.join(tickers)}", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(4)

    # --- Agent Sections ---
    sections = [
        ("MACRO  //  Senior Macro Strategist", "macro", (180, 120, 0)),
        ("QUANT  //  Lead Quantitative Analyst", "quant", (0, 140, 180)),
        ("RISK  //  Chief Risk Officer", "risk", (200, 50, 50)),
        ("CIO  //  Research Summary", "cio", (0, 160, 60)),
    ]

    for title, key, color in sections:
        text = result.get(key, "")
        if not text:
            continue

        # Section header with colored bar
        pdf.set_fill_color(*color)
        pdf.rect(10, pdf.get_y(), 3, 7, style="F")
        pdf.set_x(16)
        pdf.set_font("Helvetica", "B", 11)
        pdf.set_text_color(*color)
        pdf.cell(0, 7, title, new_x="LMARGIN", new_y="NEXT")
        pdf.ln(1)

        # Body text
        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(40, 40, 40)
        cleaned = _sanitize(text.replace("\r\n", "\n").replace("\r", "\n"))
        pdf.multi_cell(0, 4.5, cleaned)
        pdf.ln(5)

    # --- Footer on every page ---
    page_count = pdf.pages_count
    for i in range(1, page_count + 1):
        pdf.page = i
        pdf.set_y(-15)
        pdf.set_font("Helvetica", "I", 7)
        pdf.set_text_color(150, 150, 150)
        pdf.cell(0, 10, f"Quant Team Research  |  Page {i}/{page_count}", align="C")

    return pdf.output()


@router.get("/export-pdf")
def export_research_pdf():
    """Export the latest research result as a PDF document."""
    if not _sessions:
        raise HTTPException(status_code=404, detail="No research session available")

    latest_id = list(_sessions.keys())[-1]
    s = _sessions[latest_id]

    if s["generating"]:
        raise HTTPException(status_code=409, detail="Research session still in progress")

    if not s["result"]:
        raise HTTPException(status_code=404, detail="No research result available")

    pdf_bytes = _build_research_pdf(s["result"])
    question_slug = (s["result"].get("question", "research") or "research")[:40]
    safe_slug = "".join(c if c.isalnum() or c in " -_" else "" for c in question_slug).strip().replace(" ", "-")
    filename = f"research-{safe_slug}.pdf"

    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
