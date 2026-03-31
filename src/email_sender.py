import logging
from pathlib import Path

from config.settings import Config
from src.utils import today_str

logger = logging.getLogger("email_sender")


class EmailSender:
    """
    Sends the newsletter as a Gmail draft using the MCP Gmail tool.
    The actual MCP tool call happens in agent.py so this module
    prepares the subject and body and returns them.
    """

    def __init__(self, config: Config):
        self.config = config

    def prepare(self, html_path: Path, excel_path: Path) -> dict:
        """Return dict with subject and html_body ready for Gmail draft."""
        run_date = today_str()

        html_content = html_path.read_text(encoding="utf-8")

        # Append a note about the Excel file at the bottom of the HTML
        excel_note = f"""
<div style="background:#e8f5e9;border:1px solid #a5d6a7;border-radius:8px;
            padding:14px;margin:16px;font-family:Arial,sans-serif;font-size:13px;color:#2e7d32;">
  <strong>📊 Excel Data File</strong><br>
  The full structured data (AI analysis + translations) has been saved to:<br>
  <code style="background:#f1f8e9;padding:2px 6px;border-radius:4px;">{excel_path}</code><br>
  <em>Open this file in Excel/Google Sheets or pass it to your next agent.</em>
</div>
"""
        full_html = html_content.replace("</body>", excel_note + "</body>")

        return {
            "subject": f"\U0001f33e Daily Agriculture Newsletter \u2014 {run_date}",
            "html_body": full_html,
            "recipient": self.config.gmail_recipient,
        }
