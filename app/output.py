import asyncio
import difflib
import hashlib
from datetime import datetime
from io import BytesIO
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from app.config import Config
from app.pool import get_pool
from app.memory import _model


def generate_pdf(title: str, content: str) -> bytes:
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, height - 50, title[:80])
    c.setFont("Helvetica", 10)
    y = height - 80
    for line in content.split("\n"):
        for chunk in [line[i:i + 95] for i in range(0, max(len(line), 1), 95)]:
            if y < 60:
                c.showPage()
                y = height - 50
            c.drawString(50, y, chunk)
            y -= 14
    c.save()
    buffer.seek(0)
    return buffer.read()


def generate_json_report(topic: str, report: str, report_id: str, created_at: datetime) -> dict:
    return {
        "report_id": report_id,
        "topic": topic,
        "report": report,
        "created_at": created_at.isoformat(),
        "word_count": len(report.split()),
        "checksum": hashlib.md5(report.encode()).hexdigest(),
    }


async def get_report_diff(config: Config, topic: str) -> str | None:
    embedding = await asyncio.to_thread(lambda: _model.encode(topic).tolist())
    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT report, created_at FROM reports
            WHERE 1 - (embedding <=> $1::vector) > $2
            ORDER BY created_at DESC LIMIT 2
            """,
            str(embedding), config.ltm_diff_threshold,
        )
        if len(rows) < 2:
            return None
        old_lines = rows[1]["report"].splitlines(keepends=True)
        new_lines = rows[0]["report"].splitlines(keepends=True)
        diff_lines = list(difflib.unified_diff(
            old_lines, new_lines,
            fromfile=f"previous ({rows[1]['created_at'].date()})",
            tofile=f"latest ({rows[0]['created_at'].date()})",
            lineterm="",
        ))
        if not diff_lines:
            return "No significant changes since last report."
        return "\n".join(diff_lines[:config.ltm_diff_limit * 10])
