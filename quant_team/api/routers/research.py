"""Research Q&A API — ask the trading team questions without executing trades."""

from __future__ import annotations

import asyncio
import io
import logging
import re
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
        "progress": {"step": "Starting...", "step_num": 0, "total_steps": 7},
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
            "progress": {"step": "", "step_num": 0, "total_steps": 7},
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


def _md_to_html(text: str) -> str:
    """Convert markdown-ish agent output to simple HTML for fpdf2's write_html."""
    text = _sanitize(text.replace("\r\n", "\n").replace("\r", "\n"))

    lines = text.split("\n")
    html_lines: list[str] = []
    in_list = False

    for line in lines:
        stripped = line.strip()

        # Blank line — close list if open, add spacing
        if not stripped:
            if in_list:
                html_lines.append("</ul>")
                in_list = False
            html_lines.append("<br>")
            continue

        # Headings: ### or **HEADING** on its own line
        if re.match(r"^#{1,4}\s+", stripped):
            heading_text = re.sub(r"^#{1,4}\s+", "", stripped)
            if in_list:
                html_lines.append("</ul>")
                in_list = False
            html_lines.append(f'<b><font size="11">{heading_text}</font></b><br>')
            continue

        # Standalone bold line (like **KEY FINDINGS**)
        bold_match = re.match(r"^\*\*(.+)\*\*\s*$", stripped)
        if bold_match:
            if in_list:
                html_lines.append("</ul>")
                in_list = False
            html_lines.append(f'<br><b><font size="10">{bold_match.group(1)}</font></b><br>')
            continue

        # Bullet points: - or * at start
        bullet_match = re.match(r"^[-*]\s+(.+)$", stripped)
        if bullet_match:
            if not in_list:
                html_lines.append("<ul>")
                in_list = True
            bullet_content = bullet_match.group(1)
            # Inline bold within bullets
            bullet_content = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", bullet_content)
            html_lines.append(f"<li>{bullet_content}</li>")
            continue

        # Regular paragraph — close list if open
        if in_list:
            html_lines.append("</ul>")
            in_list = False

        # Inline bold
        para = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", stripped)
        html_lines.append(f"{para}<br>")

    if in_list:
        html_lines.append("</ul>")

    return "\n".join(html_lines)


def _extract_cio_sections(cio_text: str) -> dict[str, str]:
    """Parse structured sections from CIO output."""
    sections: dict[str, str] = {}
    current_key = ""
    current_lines: list[str] = []
    markers = {
        "KEY FINDINGS": "key_findings",
        "OPPORTUNITIES": "opportunities",
        "RISKS": "risks",
        "ACTIONABLE IDEAS": "actionable_ideas",
    }
    for line in cio_text.split("\n"):
        stripped = line.strip().strip("*").strip("#").strip()
        matched = False
        for marker, key in markers.items():
            if marker in stripped.upper():
                if current_key:
                    sections[current_key] = "\n".join(current_lines).strip()
                current_key = key
                current_lines = []
                matched = True
                break
        if not matched:
            current_lines.append(line)
    if current_key:
        sections[current_key] = "\n".join(current_lines).strip()
    return sections


# -- Colors matching the terminal theme --
_GREEN = (0, 180, 65)
_GREEN_DARK = (0, 60, 25)
_GREEN_DIM = (0, 120, 45)
_AMBER = (200, 140, 0)
_CYAN = (0, 150, 190)
_RED = (200, 50, 50)
_DARK = (20, 28, 40)
_DIM = (100, 110, 120)
_TEXT = (40, 45, 50)


def _render_header(pdf: FPDF, timestamp: str, tickers: list[str]) -> None:
    """Render the dark branded header banner."""
    banner_h = 38
    pdf.set_fill_color(*_DARK)
    pdf.rect(0, 0, 210, banner_h, style="F")
    pdf.set_fill_color(*_GREEN)
    pdf.rect(0, banner_h, 210, 1.2, style="F")

    pdf.set_y(8)
    pdf.set_font("Courier", "B", 16)
    pdf.set_text_color(*_GREEN)
    pdf.cell(0, 7, "  > QUANT_TEAM", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Courier", "", 8)
    pdf.set_text_color(120, 140, 120)
    pdf.cell(0, 4, "    // investment research newsletter", new_x="LMARGIN", new_y="NEXT")

    pdf.set_y(10)
    pdf.set_font("Courier", "", 7)
    pdf.set_text_color(100, 120, 100)
    pdf.cell(0, 4, timestamp, align="R", new_x="LMARGIN", new_y="NEXT")
    if tickers:
        pdf.cell(0, 4, "  ".join(tickers), align="R", new_x="LMARGIN", new_y="NEXT")

    pdf.set_y(banner_h + 6)


def _render_footer(pdf: FPDF, timestamp: str) -> None:
    """Render the dark branded footer on every page."""
    pdf.set_auto_page_break(auto=False)
    page_count = pdf.pages_count
    for i in range(1, page_count + 1):
        pdf.page = i
        pdf.set_fill_color(*_DARK)
        pdf.rect(0, 284, 210, 13, style="F")
        pdf.set_fill_color(*_GREEN)
        pdf.rect(0, 284, 210, 0.5, style="F")
        pdf.set_y(286)
        pdf.set_font("Courier", "", 6.5)
        pdf.set_text_color(*_GREEN)
        pdf.cell(95, 4, "  > QUANT_TEAM // terminal", new_x="RIGHT")
        pdf.set_text_color(100, 120, 100)
        pdf.cell(95, 4, f"page {i}/{page_count}  |  {timestamp}", align="R")


def _render_agent_appendix(pdf: FPDF, result: dict) -> None:
    """Render raw agent notes as a compact appendix."""
    r, g, b = _TEXT
    text_hex = f"#{r:02x}{g:02x}{b:02x}"

    # Appendix header
    pdf.set_draw_color(*_GREEN)
    pdf.set_line_width(0.3)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(4)
    pdf.set_font("Courier", "B", 8)
    pdf.set_text_color(*_GREEN_DIM)
    pdf.cell(0, 5, "> APPENDIX: RAW AGENT NOTES", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)

    agent_sections = [
        ("MACRO  //  Senior Macro Strategist", "macro", _AMBER),
        ("QUANT  //  Lead Quantitative Analyst", "quant", _CYAN),
        ("RISK  //  Chief Risk Officer", "risk", _RED),
        ("CIO  //  Chief Investment Officer", "cio", _GREEN),
    ]

    for title, key, color in agent_sections:
        text = result.get(key, "")
        if not text:
            continue

        pdf.set_fill_color(*color)
        pdf.rect(10, pdf.get_y(), 2, 5, style="F")
        pdf.set_x(14)
        pdf.set_font("Courier", "B", 8)
        pdf.set_text_color(*color)
        pdf.cell(0, 5, title, new_x="LMARGIN", new_y="NEXT")
        pdf.ln(1)

        pdf.set_font("Helvetica", "", 8)
        pdf.set_text_color(*_TEXT)
        html = _md_to_html(text)
        pdf.write_html(f'<font color="{text_hex}" size="8">{html}</font>')
        pdf.ln(4)


def _build_research_pdf(result: dict) -> bytes:
    """Build a branded PDF from research session results."""
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=30)
    pdf.add_page()

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    question = result.get("question", "")
    tickers = result.get("tickers_analyzed", [])
    newsletter = result.get("newsletter", "")

    r, g, b = _TEXT
    text_hex = f"#{r:02x}{g:02x}{b:02x}"

    # =====================================================================
    #  HEADER
    # =====================================================================
    _render_header(pdf, timestamp, tickers)

    # =====================================================================
    #  RESEARCH QUESTION
    # =====================================================================
    if question:
        pdf.set_font("Courier", "B", 8)
        pdf.set_text_color(*_GREEN_DIM)
        pdf.cell(0, 5, "> QUERY", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 11)
        pdf.set_text_color(*_DARK)
        pdf.multi_cell(0, 5.5, _sanitize(question))
        pdf.ln(5)

    # =====================================================================
    #  MAIN BODY — newsletter or fallback to summary + raw agents
    # =====================================================================
    if newsletter:
        # Newsletter is the primary content
        pdf.set_font("Helvetica", "", 10)
        pdf.set_text_color(*_TEXT)
        html = _md_to_html(newsletter)
        pdf.write_html(f'<font color="{text_hex}" size="10">{html}</font>')
        pdf.ln(6)

        # Raw agent notes as appendix
        _render_agent_appendix(pdf, result)
    else:
        # Fallback — no newsletter, use old executive summary + full agents
        cio_text = result.get("cio", "")
        cio_sections = _extract_cio_sections(cio_text)
        _render_summary_box(pdf, cio_sections, cio_text)

        pdf.set_font("Courier", "B", 9)
        pdf.set_text_color(*_GREEN_DIM)
        pdf.cell(0, 6, "> FULL AGENT ANALYSIS", new_x="LMARGIN", new_y="NEXT")
        pdf.set_draw_color(*_GREEN)
        pdf.set_line_width(0.3)
        pdf.line(10, pdf.get_y(), 200, pdf.get_y())
        pdf.ln(4)

        for title, key, color in [
            ("MACRO  //  Senior Macro Strategist", "macro", _AMBER),
            ("QUANT  //  Lead Quantitative Analyst", "quant", _CYAN),
            ("RISK  //  Chief Risk Officer", "risk", _RED),
            ("CIO  //  Chief Investment Officer", "cio", _GREEN),
        ]:
            text = result.get(key, "")
            if not text:
                continue
            pdf.set_fill_color(*color)
            pdf.rect(10, pdf.get_y(), 2.5, 6, style="F")
            pdf.set_x(15)
            pdf.set_font("Courier", "B", 9)
            pdf.set_text_color(*color)
            pdf.cell(0, 6, title, new_x="LMARGIN", new_y="NEXT")
            pdf.ln(1)
            pdf.set_font("Helvetica", "", 9)
            html = _md_to_html(text)
            pdf.write_html(f'<font color="{text_hex}" size="9">{html}</font>')
            pdf.ln(6)

    # =====================================================================
    #  FOOTER
    # =====================================================================
    _render_footer(pdf, timestamp)

    return pdf.output()


def _render_summary_box(pdf: FPDF, sections: dict[str, str], cio_text: str) -> None:
    """Render the executive summary box with key takeaways and trade recs."""
    key_findings = sections.get("key_findings", "")
    actionable = sections.get("actionable_ideas", "")
    risks = sections.get("risks", "")

    if not key_findings and not actionable:
        return

    # Box background — light green tint
    box_y = pdf.get_y()
    pdf.set_fill_color(240, 250, 242)
    pdf.set_draw_color(*_GREEN)
    pdf.set_line_width(0.4)

    # We need to calculate height, so render into a temp position
    # Use a fixed generous estimate then draw box behind
    start_y = box_y

    # Draw box border (left accent bar)
    pdf.set_fill_color(*_GREEN)
    pdf.rect(10, start_y, 2.5, 3, style="F")  # placeholder, will extend

    pdf.set_x(15)
    pdf.set_font("Courier", "B", 10)
    pdf.set_text_color(*_GREEN_DARK)
    pdf.cell(0, 6, "> EXECUTIVE SUMMARY", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(1)

    r, g, b = _TEXT
    text_hex = f"#{r:02x}{g:02x}{b:02x}"

    # Key Takeaways
    if key_findings:
        pdf.set_x(15)
        pdf.set_font("Courier", "B", 8)
        pdf.set_text_color(*_DARK)
        pdf.cell(0, 5, "KEY TAKEAWAYS", new_x="LMARGIN", new_y="NEXT")
        pdf.set_x(15)
        pdf.set_font("Helvetica", "", 9)
        html = _md_to_html(key_findings)
        pdf.write_html(f'<font color="{text_hex}" size="9">{html}</font>')
        pdf.ln(3)

    # Trade Recommendations
    if actionable:
        pdf.set_x(15)
        pdf.set_font("Courier", "B", 8)
        pdf.set_text_color(*_GREEN_DARK)
        pdf.cell(0, 5, "TRADE RECOMMENDATIONS", new_x="LMARGIN", new_y="NEXT")
        pdf.set_x(15)
        pdf.set_font("Helvetica", "", 9)
        html = _md_to_html(actionable)
        pdf.write_html(f'<font color="{text_hex}" size="9">{html}</font>')
        pdf.ln(3)

    # Key Risks (brief)
    if risks:
        pdf.set_x(15)
        pdf.set_font("Courier", "B", 8)
        rr, rg, rb = _RED
        pdf.set_text_color(*_RED)
        pdf.cell(0, 5, "KEY RISKS", new_x="LMARGIN", new_y="NEXT")
        pdf.set_x(15)
        pdf.set_font("Helvetica", "", 9)
        html = _md_to_html(risks)
        pdf.write_html(f'<font color="{text_hex}" size="9">{html}</font>')
        pdf.ln(2)

    end_y = pdf.get_y()

    # Draw the green accent bar the full height of the summary box
    pdf.set_fill_color(*_GREEN)
    pdf.rect(10, start_y, 2.5, end_y - start_y, style="F")

    # Draw a light background behind the box (rendered below text, so we
    # draw a subtle bottom border instead to avoid overlapping)
    pdf.set_draw_color(200, 220, 200)
    pdf.set_line_width(0.3)
    pdf.line(10, end_y + 1, 200, end_y + 1)

    pdf.ln(6)


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
