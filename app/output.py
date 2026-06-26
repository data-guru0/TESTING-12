import asyncio
import hashlib
from datetime import datetime
from io import BytesIO
import asyncpg
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from app.config import Config


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
    from app.memory import _model
    embedding = await asyncio.to_thread(lambda: _model.encode(topic).tolist())
    conn = await asyncpg.connect(config.database_url)
    try:
        rows = await conn.fetch(
            """SELECT report, created_at FROM reports
               WHERE 1 - (embedding <=> $1::vector) > 0.7
               ORDER BY created_at DESC LIMIT 2""",
            str(embedding),
        )
        if len(rows) < 2:
            return None
        old_set = set(rows[1]["report"].split(". "))
        new_set = set(rows[0]["report"].split(". "))
        added = [f"[NEW] {s}" for s in list(new_set - old_set)[:5]]
        removed = [f"[REMOVED] {s}" for s in list(old_set - new_set)[:5]]
        diff = "\n".join(added + removed)
        return diff if diff.strip() else "No significant changes since last report."
    finally:
        await conn.close()
