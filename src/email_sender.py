"""
EmailSender — saves newsletter payload to output/pending_email.json
The actual Gmail draft is created by Claude Code via MCP after each agent run.
"""

import json
import logging
from pathlib import Path

from config.settings import Config
from src.utils import today_str

logger = logging.getLogger("email_sender")


class EmailSender:
    def __init__(self, config: Config):
        self.config = config
        self.pending_path = config.output_dir / "pending_email.json"

    def prepare(self, html_path: Path, excel_path: Path) -> dict:
        run_date = today_str()
        html_content = html_path.read_text(encoding="utf-8")

        # Append Excel reference note inside the HTML
        excel_note = f"""
<div style="background:#e8f5e9;border:1px solid #a5d6a7;border-radius:8px;
            padding:14px;margin:16px;font-family:Arial,sans-serif;font-size:13px;color:#2e7d32;">
  <strong>📊 Excel Data File</strong><br>
  Full AI analysis + translations saved to:<br>
  <code style="background:#f1f8e9;padding:2px 6px;border-radius:4px;">{excel_path.name}</code><br>
  <em>Open in Excel/Google Sheets or pass to your next agent.</em>
</div>"""
        full_html = html_content.replace("</body>", excel_note + "\n</body>")

        payload = {
            "to": self.config.gmail_recipient,
            "subject": f"\U0001f33e Daily Agriculture Newsletter \u2014 {run_date}",
            "html_body": full_html,
            "run_date": run_date,
            "html_path": str(html_path),
            "excel_path": str(excel_path),
            "sent": False,
        }

        # Save payload for MCP pick-up
        self.pending_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        logger.info(f"Email payload saved → {self.pending_path}")
        return payload

    def mark_sent(self, draft_id: str):
        if self.pending_path.exists():
            data = json.loads(self.pending_path.read_text())
            data["sent"] = True
            data["draft_id"] = draft_id
            self.pending_path.write_text(json.dumps(data, indent=2))
            logger.info(f"Gmail draft created: {draft_id}")
