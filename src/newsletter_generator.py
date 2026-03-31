import logging
from datetime import date
from pathlib import Path

from config.settings import Config
from src.utils import today_str, format_date_display

logger = logging.getLogger("newsletter_generator")

SENTIMENT_COLORS = {
    "positive": "#2e7d32",
    "neutral": "#f57c00",
    "negative": "#c62828",
}

SUBCATEGORY_ICONS = {
    "Crop Prices": "💰",
    "Government Policy": "🏛️",
    "Weather & Climate": "🌦️",
    "Market & Trade": "📊",
    "Technology": "🔬",
    "General": "📰",
}


def _sentiment_badge(sentiment: str) -> str:
    color = SENTIMENT_COLORS.get(sentiment, "#888")
    label = sentiment.capitalize()
    return f'<span style="background:{color};color:#fff;padding:2px 8px;border-radius:12px;font-size:11px;font-weight:600;">{label}</span>'


def _importance_bar(score: int) -> str:
    pct = int(score * 10)
    color = "#2e7d32" if score >= 7 else ("#f57c00" if score >= 4 else "#c62828")
    return f'''<div style="margin:4px 0 8px;">
      <span style="font-size:11px;color:#666;">Importance: {score}/10</span>
      <div style="background:#e0e0e0;border-radius:4px;height:5px;margin-top:3px;">
        <div style="background:{color};width:{pct}%;height:5px;border-radius:4px;"></div>
      </div>
    </div>'''


def _tags_html(tags: list) -> str:
    if not tags:
        return ""
    chips = "".join(
        f'<span style="background:#e8f5e9;color:#2e7d32;padding:2px 8px;border-radius:10px;font-size:11px;margin:2px;">{t}</span>'
        for t in tags
    )
    return f'<div style="margin-top:8px;">{chips}</div>'


def _article_card(article, lang: str) -> str:
    if lang == "en" or not article.translations.get(lang):
        title = article.title
        summary = article.summary_en
        key_points = article.key_points
    else:
        t = article.translations[lang]
        title = t.get("title", article.title)
        summary = t.get("summary", article.summary_en)
        key_points = t.get("key_points", article.key_points)

    pub = format_date_display(article.published_at)
    sentiment = article.sentiment or "neutral"
    badge = _sentiment_badge(sentiment)
    bar = _importance_bar(article.importance_score)
    tags = _tags_html(article.tags)

    kp_items = "".join(f"<li style='margin:3px 0;'>{p}</li>" for p in key_points[:5])
    kp_html = f"<ul style='margin:6px 0 0 16px;padding:0;color:#444;font-size:13px;'>{kp_items}</ul>" if kp_items else ""

    return f'''<div style="background:#fff;border:1px solid #e0e0e0;border-radius:10px;padding:16px;margin-bottom:14px;box-shadow:0 1px 3px rgba(0,0,0,0.08);">
  <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:6px;">
    <span style="font-size:11px;color:#888;">{article.source_name} &bull; {pub}</span>
    {badge}
  </div>
  {bar}
  <a href="{article.url}" target="_blank" style="font-size:16px;font-weight:700;color:#1b5e20;text-decoration:none;line-height:1.3;display:block;margin-bottom:8px;">{title}</a>
  <p style="color:#555;font-size:13px;line-height:1.6;margin:0 0 6px;">{summary}</p>
  {kp_html}
  {tags}
</div>'''


def _section(articles, subcategory: str, lang: str) -> str:
    icon = SUBCATEGORY_ICONS.get(subcategory, "📰")
    cards = "".join(_article_card(a, lang) for a in articles)
    return f'''<div style="margin-bottom:32px;">
  <h2 style="font-size:18px;color:#1b5e20;border-bottom:2px solid #a5d6a7;padding-bottom:6px;margin-bottom:16px;">{icon} {subcategory}</h2>
  {cards}
</div>'''


def _build_lang_content(articles: list, lang: str, lang_names: dict) -> str:
    from collections import defaultdict
    groups = defaultdict(list)
    for a in articles:
        groups[a.subcategory].append(a)

    order = ["Crop Prices", "Government Policy", "Market & Trade", "Weather & Climate", "Technology", "General"]
    sections = ""
    for cat in order:
        if groups[cat]:
            sections += _section(groups[cat], cat, lang)
    # Any remaining uncategorized
    for cat, arts in groups.items():
        if cat not in order:
            sections += _section(arts, cat, lang)

    return sections


def _build_html(articles: list, config: Config, run_date: str) -> str:
    langs = config.newsletter_languages
    lang_names = config.LANGUAGE_NAMES

    # Build tab buttons
    tab_buttons = ""
    for i, lang in enumerate(langs):
        name = lang_names.get(lang, lang.upper())
        active_style = "background:#2e7d32;color:#fff;" if i == 0 else "background:#f5f5f5;color:#333;"
        tab_buttons += f'<button onclick="switchLang(\'{lang}\')" id="tab-{lang}" style="{active_style}border:1px solid #ccc;padding:8px 14px;margin:3px;border-radius:20px;cursor:pointer;font-size:13px;font-family:inherit;">{name}</button>\n'

    # Build language content divs
    content_divs = ""
    for i, lang in enumerate(langs):
        display = "block" if i == 0 else "none"
        body = _build_lang_content(articles, lang, lang_names)
        content_divs += f'<div id="content-{lang}" style="display:{display};">{body}</div>\n'

    total = len(articles)
    pos = sum(1 for a in articles if a.sentiment == "positive")
    neg = sum(1 for a in articles if a.sentiment == "negative")

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Daily Agriculture Newsletter — {run_date}</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: 'Segoe UI', Arial, sans-serif; background: #f9fbe7; color: #333; }}
  @media (max-width: 600px) {{
    .stats-bar {{ flex-direction: column; }}
    .tab-wrap {{ flex-wrap: wrap; }}
  }}
</style>
</head>
<body>

<!-- Header -->
<div style="background:linear-gradient(135deg,#1b5e20,#388e3c);color:#fff;padding:28px 24px;text-align:center;">
  <div style="font-size:36px;">🌾</div>
  <h1 style="font-size:24px;font-weight:700;margin:8px 0 4px;">Daily Agriculture Newsletter</h1>
  <p style="font-size:14px;opacity:0.85;">{run_date} &bull; Powered by Claude AI</p>
</div>

<!-- Stats bar -->
<div class="stats-bar" style="background:#e8f5e9;display:flex;justify-content:center;gap:24px;padding:12px 24px;flex-wrap:wrap;border-bottom:1px solid #c8e6c9;">
  <span style="font-size:13px;color:#2e7d32;font-weight:600;">📰 {total} Articles</span>
  <span style="font-size:13px;color:#2e7d32;font-weight:600;">✅ {pos} Positive</span>
  <span style="font-size:13px;color:#c62828;font-weight:600;">⚠️ {neg} Negative</span>
  <span style="font-size:13px;color:#333;font-weight:600;">🌐 {len(langs)} Languages</span>
</div>

<!-- Language Tabs -->
<div style="background:#fff;padding:14px 24px;border-bottom:1px solid #e0e0e0;text-align:center;">
  <p style="font-size:12px;color:#888;margin-bottom:8px;">Select Language / भाषा चुनें</p>
  <div class="tab-wrap">
    {tab_buttons}
  </div>
</div>

<!-- Main Content -->
<div style="max-width:860px;margin:0 auto;padding:24px 16px;">
  {content_divs}
</div>

<!-- Footer -->
<div style="background:#1b5e20;color:#fff;text-align:center;padding:20px;font-size:12px;margin-top:32px;">
  <p>Generated by AI Agriculture Agent &bull; {run_date}</p>
  <p style="margin-top:4px;opacity:0.7;">Powered by Claude AI &bull; Data from NewsAPI & RSS feeds</p>
</div>

<script>
function switchLang(lang) {{
  document.querySelectorAll('[id^="content-"]').forEach(function(el) {{
    el.style.display = 'none';
  }});
  document.querySelectorAll('[id^="tab-"]').forEach(function(btn) {{
    btn.style.background = '#f5f5f5';
    btn.style.color = '#333';
  }});
  var content = document.getElementById('content-' + lang);
  if (content) content.style.display = 'block';
  var tab = document.getElementById('tab-' + lang);
  if (tab) {{ tab.style.background = '#2e7d32'; tab.style.color = '#fff'; }}
}}
</script>
</body>
</html>'''


class NewsletterGenerator:
    def __init__(self, config: Config):
        self.config = config
        self.output_dir = config.output_dir / "newsletters"
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate(self, articles: list) -> Path:
        run_date = today_str()
        html = _build_html(articles, self.config, run_date)
        out_path = self.output_dir / f"{run_date}_agriculture_newsletter.html"
        out_path.write_text(html, encoding="utf-8")
        logger.info(f"Newsletter saved: {out_path}")
        return out_path
