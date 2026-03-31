import hashlib
import html
import logging
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

import requests

from config.settings import Config
from config.rss_feeds import AGRICULTURE_RSS_FEEDS
from src.utils import retry_with_backoff

logger = logging.getLogger("news_fetcher")


@dataclass
class RawArticle:
    article_id: str
    title: str
    url: str
    source_name: str
    fetch_source: str          # "newsapi" | "rss"
    published_at: datetime
    description: Optional[str] = None
    content: Optional[str] = None
    image_url: Optional[str] = None
    category: str = "agriculture"


def _make_id(url: str) -> str:
    return hashlib.sha256(url.encode()).hexdigest()[:16]


def _normalize_dt(value) -> datetime:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S%z", "%a, %d %b %Y %H:%M:%S %z"):
            try:
                return datetime.strptime(value, fmt).replace(tzinfo=timezone.utc)
            except ValueError:
                continue
    return datetime.now(timezone.utc)


def _word_overlap(a: str, b: str) -> float:
    wa = set(a.lower().split())
    wb = set(b.lower().split())
    if not wa or not wb:
        return 0.0
    return len(wa & wb) / max(len(wa), len(wb))


def _deduplicate(articles: list) -> list:
    seen_urls = set()
    seen_titles = []
    result = []
    for art in articles:
        if art.url in seen_urls:
            continue
        # Near-duplicate title check
        is_dup = any(_word_overlap(art.title, t) > 0.80 for t in seen_titles)
        if is_dup:
            continue
        seen_urls.add(art.url)
        seen_titles.append(art.title)
        result.append(art)
    return result


class NewsFetcher:
    def __init__(self, config: Config):
        self.config = config

    def fetch_all(self) -> list:
        articles = []

        if self.config.newsapi_key:
            articles.extend(self._fetch_newsapi())
        else:
            logger.warning("NEWSAPI_KEY not set — skipping NewsAPI, using RSS only")

        articles.extend(self._fetch_rss())

        articles = _deduplicate(articles)
        articles.sort(key=lambda a: a.published_at, reverse=True)
        articles = articles[:self.config.newsapi_max_articles]

        logger.info(f"Fetched {len(articles)} unique agriculture articles")
        return articles

    @retry_with_backoff(max_retries=3, base_delay=2.0)
    def _fetch_newsapi(self) -> list:
        articles = []
        url = "https://newsapi.org/v2/everything"
        params = {
            "q": self.config.news_query,
            "language": "en",
            "sortBy": "publishedAt",
            "pageSize": min(self.config.newsapi_max_articles, 100),
            "apiKey": self.config.newsapi_key,
        }
        try:
            resp = requests.get(url, params=params, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            for item in data.get("articles", []):
                if not item.get("url") or item.get("title") == "[Removed]":
                    continue
                articles.append(RawArticle(
                    article_id=_make_id(item["url"]),
                    title=item.get("title", "Untitled"),
                    url=item["url"],
                    source_name=item.get("source", {}).get("name", "NewsAPI"),
                    fetch_source="newsapi",
                    published_at=_normalize_dt(item.get("publishedAt", "")),
                    description=item.get("description"),
                    content=item.get("content"),
                    image_url=item.get("urlToImage"),
                ))
            logger.info(f"NewsAPI returned {len(articles)} articles")
        except Exception as e:
            logger.error(f"NewsAPI fetch failed: {e}")
        return articles

    def _fetch_rss(self) -> list:
        articles = []
        for feed_url in AGRICULTURE_RSS_FEEDS:
            try:
                resp = requests.get(feed_url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
                resp.raise_for_status()
                count = 0
                parsed = _parse_rss_xml(resp.content, feed_url)
                for item in parsed[:10]:
                    if not item.get("url") or not item.get("title"):
                        continue
                    articles.append(RawArticle(
                        article_id=_make_id(item["url"]),
                        title=item["title"],
                        url=item["url"],
                        source_name=item.get("feed_title", feed_url.split("/")[2]),
                        fetch_source="rss",
                        published_at=_normalize_dt(item.get("published")) if item.get("published") else datetime.now(timezone.utc),
                        description=item.get("description"),
                        image_url=None,
                    ))
                    count += 1
                if count:
                    logger.debug(f"RSS {feed_url[:50]}... → {count} articles")
            except Exception as e:
                logger.warning(f"RSS feed failed ({feed_url[:50]}...): {e}")
        logger.info(f"RSS feeds returned {len(articles)} articles")
        return articles


def _strip_tags(text: str) -> str:
    """Remove HTML tags and unescape entities."""
    if not text:
        return ""
    clean = re.sub(r"<[^>]+>", " ", text)
    return html.unescape(clean).strip()


def _parse_rss_xml(content: bytes, feed_url: str) -> list:
    """Parse RSS/Atom XML using stdlib xml.etree.ElementTree."""
    items = []
    try:
        root = ET.fromstring(content)
    except ET.ParseError:
        return items

    ns = {"atom": "http://www.w3.org/2005/Atom"}
    feed_title = ""

    # RSS 2.0
    channel = root.find("channel")
    if channel is not None:
        feed_title = (channel.findtext("title") or "").strip()
        for item in channel.findall("item"):
            items.append({
                "title": _strip_tags(item.findtext("title") or ""),
                "url": (item.findtext("link") or "").strip(),
                "description": _strip_tags(item.findtext("description") or ""),
                "published": item.findtext("pubDate") or item.findtext("dc:date", namespaces={"dc": "http://purl.org/dc/elements/1.1/"}),
                "feed_title": feed_title,
            })
        return items

    # Atom
    atom_ns = "http://www.w3.org/2005/Atom"
    feed_title_el = root.find(f"{{{atom_ns}}}title")
    if feed_title_el is not None:
        feed_title = (feed_title_el.text or "").strip()
    for entry in root.findall(f"{{{atom_ns}}}entry"):
        link_el = entry.find(f"{{{atom_ns}}}link")
        url = link_el.get("href", "") if link_el is not None else ""
        title_el = entry.find(f"{{{atom_ns}}}title")
        title = _strip_tags(title_el.text or "") if title_el is not None else ""
        summary_el = entry.find(f"{{{atom_ns}}}summary") or entry.find(f"{{{atom_ns}}}content")
        desc = _strip_tags(summary_el.text or "") if summary_el is not None else ""
        pub_el = entry.find(f"{{{atom_ns}}}published") or entry.find(f"{{{atom_ns}}}updated")
        pub = pub_el.text if pub_el is not None else None
        items.append({"title": title, "url": url, "description": desc, "published": pub, "feed_title": feed_title})

    return items
