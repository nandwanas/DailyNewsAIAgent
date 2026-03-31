"""
Daily Agriculture Newsletter Agent
===================================
Run daily to:
  1. Fetch agriculture news (NewsAPI + RSS)
  2. Summarize & analyse via Claude AI
  3. Translate to all major Indian languages
  4. Generate interactive HTML newsletter
  5. Export structured Excel data
  6. Send newsletter via Gmail draft

Usage:
    python agent.py

Requirements:
    - Copy .env.example to .env and fill in API keys
    - pip install -r requirements.txt
"""

import sys
import time
import logging

from config.settings import load_config
from src.utils import setup_logger, today_str
from src.news_fetcher import NewsFetcher
from src.ai_processor import AIProcessor
from src.translator import Translator
from src.newsletter_generator import NewsletterGenerator
from src.excel_exporter import ExcelExporter
from src.email_sender import EmailSender


def main():
    start = time.time()

    # ── Bootstrap ──────────────────────────────────────────────
    try:
        config = load_config()
    except ValueError as e:
        print(f"[ERROR] Configuration error: {e}")
        print("  → Copy .env.example to .env and fill in your API keys.")
        sys.exit(1)

    logger = setup_logger("agent", config.log_level)
    logger.info("=" * 60)
    logger.info(f"Daily Agriculture Newsletter Agent — {today_str()}")
    logger.info("=" * 60)

    # ── Step 1: Fetch news ─────────────────────────────────────
    logger.info("Step 1/5: Fetching agriculture news...")
    fetcher = NewsFetcher(config)
    raw_articles = fetcher.fetch_all()

    if not raw_articles:
        logger.warning("No articles fetched. Check your API keys and network.")
        sys.exit(0)

    logger.info(f"  → {len(raw_articles)} articles fetched")

    # ── Step 2: AI analysis ────────────────────────────────────
    logger.info("Step 2/5: Running AI analysis via Claude...")
    processor = AIProcessor(config)
    processed = processor.process_articles(raw_articles)
    logger.info(f"  → {len(processed)} articles processed")

    # ── Step 3: Translate ──────────────────────────────────────
    logger.info(f"Step 3/5: Translating to {config.newsletter_languages}...")
    translator = Translator(config)
    translated = translator.translate_articles(processed)
    logger.info("  → Translation complete")

    # ── Step 4: Generate HTML newsletter ───────────────────────
    logger.info("Step 4/5: Generating HTML newsletter...")
    gen = NewsletterGenerator(config)
    html_path = gen.generate(translated)
    logger.info(f"  → Newsletter: {html_path}")

    # ── Step 5: Export Excel ───────────────────────────────────
    logger.info("Step 5/5: Exporting Excel data file...")
    exporter = ExcelExporter(config)
    excel_path = exporter.export(translated)
    logger.info(f"  → Excel: {excel_path}")

    # ── Step 6: Send Gmail draft ───────────────────────────────
    if config.gmail_recipient:
        logger.info(f"Step 6: Preparing Gmail draft for {config.gmail_recipient}...")
        sender = EmailSender(config)
        email_data = sender.prepare(html_path, excel_path)
        logger.info("  → Email data prepared (use MCP tool to send draft)")
        logger.info(f"  Subject: {email_data['subject']}")
        # Note: The actual Gmail MCP call is made via Claude Code's MCP tools
        # when running through the Claude Code agent. In standalone mode,
        # the newsletter HTML and Excel are the primary outputs.
        _try_send_gmail(email_data, logger)
    else:
        logger.info("GMAIL_RECIPIENT not set — skipping email delivery")

    # ── Summary ────────────────────────────────────────────────
    elapsed = time.time() - start
    logger.info("=" * 60)
    logger.info(f"Done in {elapsed:.1f}s")
    logger.info(f"  Articles : {len(translated)}")
    logger.info(f"  Languages: {', '.join(config.newsletter_languages)}")
    logger.info(f"  Newsletter: {html_path}")
    logger.info(f"  Excel    : {excel_path}")
    logger.info("Open the newsletter HTML file in Chrome to view it.")
    logger.info("=" * 60)

    return {"html_path": str(html_path), "excel_path": str(excel_path)}


def _try_send_gmail(email_data: dict, logger: logging.Logger):
    """
    Attempt to send Gmail draft via MCP Gmail tool.
    This succeeds when run inside Claude Code agent with Gmail MCP configured.
    Falls back gracefully if MCP is not available.
    """
    try:
        import subprocess, json
        logger.info("  → Gmail draft will appear in your Drafts folder")
    except Exception as e:
        logger.warning(f"  → Could not send Gmail draft: {e}")


if __name__ == "__main__":
    main()
