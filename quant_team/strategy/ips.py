"""Investment Policy Statement generation and evolution."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from sqlalchemy.orm import Session

from ..agents.base import Agent, Message
from ..database.models import Recommendation, TradeRecord

IPS_TEMPLATE = """You are collaborating with your team to draft an Investment Policy Statement (IPS) for an autonomous stock and options trading portfolio.

The IPS must cover:

1. **Investment Objectives** — Return target, risk tolerance, time horizon, benchmark (S&P 500)
2. **Investment Universe** — US equities + listed options. Excluded: shorting, futures, naked short options, penny stocks
3. **Asset Allocation** — Equities, options, cash ranges. Sector limits. Rebalancing triggers.
4. **Trading Strategies** — Momentum, value, earnings plays, sector rotation, options strategies
5. **Risk Management** — Position sizing, stop-losses (8% max), options max loss (5%), drawdown plan
6. **PDT Rules** — Max 3 day trades per 5 business days. Prefer swing trades.
7. **Performance Monitoring** — Review frequency, metrics, strategy retirement criteria

Starting capital: $10,000 (autonomous trading — decisions execute automatically)

Provide your section from your area of expertise. Be specific with numbers and rules."""


def generate_ips(agents: list[Agent], data_dir: str = "data") -> str:
    """Have the team collaboratively draft an IPS."""
    data_path = Path(data_dir)
    data_path.mkdir(exist_ok=True)

    discussion: list[Message] = []

    for agent in agents:
        prompt_parts = [IPS_TEMPLATE]
        if discussion:
            prompt_parts.append("\n## Team Input So Far")
            for msg in discussion:
                prompt_parts.append(f"**{msg.role}**: {msg.content}")
            prompt_parts.append(
                f"\nNow provide YOUR section as the {agent.title}. "
                "Build on what your colleagues have said. Be specific."
            )

        response = agent.respond("\n\n".join(prompt_parts))
        discussion.append(Message(role=agent.name, content=response))

    cio = agents[0]
    synthesis_prompt = (
        "Synthesize a FINAL Investment Policy Statement for our $10,000 autonomous trading portfolio. "
        "Key constraints: NO shorting, NO futures, NO naked short options, PDT rules apply.\n\n"
        "## Team Input\n\n"
    )
    for msg in discussion:
        synthesis_prompt += f"**{msg.role}**: {msg.content}\n\n"

    final_ips = cio.respond(synthesis_prompt)

    (data_path / "ips.md").write_text(final_ips)
    log = {
        "generated_at": datetime.utcnow().isoformat(),
        "discussion": [{"role": m.role, "content": m.content} for m in discussion],
        "final_ips": final_ips,
    }
    (data_path / "ips_log.json").write_text(json.dumps(log, indent=2))

    return final_ips


def evolve_ips(cio_agent: Agent, db: Session, data_dir: str = "data") -> str:
    """Have the CIO review and update the IPS based on recent performance.

    This runs after trading sessions to adapt strategy to changing conditions.
    """
    data_path = Path(data_dir)
    ips_path = data_path / "ips.md"

    # Load current IPS
    current_ips = ""
    if ips_path.exists():
        current_ips = ips_path.read_text()

    if not current_ips:
        return ""  # No IPS to evolve

    # Gather recent performance data
    recent_trades = (
        db.query(TradeRecord)
        .order_by(TradeRecord.timestamp.desc())
        .limit(20)
        .all()
    )

    recent_recs = (
        db.query(Recommendation)
        .filter(Recommendation.status.in_(["executed", "blocked"]))
        .order_by(Recommendation.created_at.desc())
        .limit(20)
        .all()
    )

    # Build performance summary
    perf_lines = ["## Recent Trading Performance"]

    if recent_trades:
        total_pnl = sum(t.pnl for t in recent_trades if t.action == "SELL")
        wins = sum(1 for t in recent_trades if t.action == "SELL" and t.pnl > 0)
        losses = sum(1 for t in recent_trades if t.action == "SELL" and t.pnl <= 0)
        total_sells = wins + losses
        win_rate = (wins / total_sells * 100) if total_sells > 0 else 0

        perf_lines.append(f"- Closed trades: {total_sells}")
        perf_lines.append(f"- Win rate: {win_rate:.0f}%")
        perf_lines.append(f"- Total P&L: ${total_pnl:,.2f}")
        perf_lines.append("")
        perf_lines.append("### Recent Trades")
        for t in recent_trades[:10]:
            perf_lines.append(
                f"- {t.action} {t.ticker} ({t.position_type}) @ ${t.price:.2f} "
                f"| P&L: ${t.pnl:.2f} | {t.reasoning or ''}"
            )
    else:
        perf_lines.append("- No completed trades yet")

    blocked = [r for r in recent_recs if r.status == "blocked"]
    if blocked:
        perf_lines.append("\n### Blocked Decisions")
        for r in blocked[:5]:
            perf_lines.append(f"- {r.action} {r.ticker}: {r.reasoning}")

    performance_summary = "\n".join(perf_lines)

    # Ask CIO to evolve the IPS
    evolution_prompt = (
        "You are reviewing and updating your Investment Policy Statement based on recent performance.\n\n"
        f"## Current IPS\n{current_ips}\n\n"
        f"{performance_summary}\n\n"
        "## Your Task\n"
        "Review the current IPS and recent performance. Update the IPS to:\n"
        "1. Adjust strategies that are working well (double down)\n"
        "2. Modify or retire strategies that are underperforming\n"
        "3. Update sector/market outlook based on what you've observed\n"
        "4. Refine position sizing or risk parameters if needed\n"
        "5. Add any new rules learned from blocked trades\n\n"
        "Output the COMPLETE updated IPS document. Keep the same structure but evolve the content.\n"
        "Mark sections you changed with [UPDATED] tags so the team can track evolution.\n"
        "Key constraints remain: NO shorting, NO futures, NO naked short options, PDT rules apply."
    )

    updated_ips = cio_agent.respond(evolution_prompt)

    # Save updated IPS
    ips_path.write_text(updated_ips)

    # Log the evolution
    log_path = data_path / "ips_log.json"
    log = {"entries": []}
    if log_path.exists():
        try:
            log = json.loads(log_path.read_text())
            if not isinstance(log, dict):
                log = {"entries": [log] if isinstance(log, list) else []}
        except (json.JSONDecodeError, TypeError):
            log = {"entries": []}

    if "entries" not in log:
        log["entries"] = []

    log["entries"].append({
        "evolved_at": datetime.utcnow().isoformat(),
        "performance_summary": performance_summary,
        "updated_ips": updated_ips[:2000],  # Truncate for log
    })

    log_path.write_text(json.dumps(log, indent=2))

    return updated_ips
