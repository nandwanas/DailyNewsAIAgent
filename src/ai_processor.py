import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

import anthropic

from config.settings import Config
from src.news_fetcher import RawArticle
from src.utils import retry_with_backoff

logger = logging.getLogger("ai_processor")


@dataclass
class ProcessedArticle:
    # Raw fields
    article_id: str
    title: str
    url: str
    source_name: str
    fetch_source: str
    published_at: datetime
    description: Optional[str]
    content: Optional[str]
    image_url: Optional[str]
    category: str

    # AI analysis
    summary_en: str = ""
    key_points: list = field(default_factory=list)
    sentiment: str = "neutral"
    sentiment_score: float = 0.0
    importance_score: int = 5
    tags: list = field(default_factory=list)
    subcategory: str = "General"

    # Translations filled by translator
    translations: dict = field(default_factory=dict)

    # Metadata
    processed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    processing_errors: list = field(default_factory=list)


def _extract_json(text: str) -> dict:
    """Extract JSON from Claude response, handling markdown code fences."""
    text = text.strip()
    # Try to find JSON in code fences
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if match:
        text = match.group(1)
    # Try direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Find first { ... } block
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1:
            try:
                return json.loads(text[start:end+1])
            except json.JSONDecodeError:
                pass
    return {}


ANALYSIS_PROMPT = """You are an expert agriculture news analyst. Analyze the following news article and return ONLY valid JSON — no explanation, no prose.

Title: {title}
Source: {source}
Content: {content}

Return this exact JSON structure:
{{
  "summary_en": "2-3 sentence factual summary in English",
  "key_points": ["point 1", "point 2", "point 3"],
  "sentiment": "positive",
  "sentiment_score": 0.5,
  "importance_score": 7,
  "tags": ["wheat", "MSP", "India"],
  "subcategory": "Crop Prices"
}}

Rules:
- sentiment must be exactly: "positive", "negative", or "neutral"
- sentiment_score: float from -1.0 (very negative) to 1.0 (very positive)
- importance_score: integer 1-10 (10 = most important for Indian farmers)
- tags: 3-5 relevant agriculture keywords
- subcategory: one of: "Crop Prices", "Government Policy", "Weather & Climate", "Market & Trade", "Technology", "General"
"""


class AIProcessor:
    def __init__(self, config: Config):
        self.client = anthropic.Anthropic(api_key=config.anthropic_api_key)
        self.model = config.claude_model

    def process_articles(self, raw_articles: list) -> list:
        processed = []
        total = len(raw_articles)
        for i, article in enumerate(raw_articles, 1):
            logger.info(f"Processing article {i}/{total}: {article.title[:60]}...")
            try:
                result = self._process_single(article)
                processed.append(result)
            except Exception as e:
                logger.error(f"Failed to process article '{article.title[:40]}': {e}")
                # Still include the article with defaults
                processed.append(self._make_default(article, str(e)))
        logger.info(f"AI processing complete: {len(processed)} articles")
        return processed

    @retry_with_backoff(max_retries=3, base_delay=3.0)
    def _process_single(self, article: RawArticle) -> ProcessedArticle:
        body = article.content or article.description or article.title
        prompt = ANALYSIS_PROMPT.format(
            title=article.title,
            source=article.source_name,
            content=body[:2000],
        )
        response = self.client.messages.create(
            model=self.model,
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}]
        )
        raw_text = response.content[0].text
        data = _extract_json(raw_text)

        return ProcessedArticle(
            article_id=article.article_id,
            title=article.title,
            url=article.url,
            source_name=article.source_name,
            fetch_source=article.fetch_source,
            published_at=article.published_at,
            description=article.description,
            content=article.content,
            image_url=article.image_url,
            category=article.category,
            summary_en=data.get("summary_en", article.description or ""),
            key_points=data.get("key_points", [])[:5],
            sentiment=data.get("sentiment", "neutral"),
            sentiment_score=float(data.get("sentiment_score", 0.0)),
            importance_score=int(data.get("importance_score", 5)),
            tags=data.get("tags", [])[:5],
            subcategory=data.get("subcategory", "General"),
        )

    def _make_default(self, article: RawArticle, error: str) -> ProcessedArticle:
        return ProcessedArticle(
            article_id=article.article_id,
            title=article.title,
            url=article.url,
            source_name=article.source_name,
            fetch_source=article.fetch_source,
            published_at=article.published_at,
            description=article.description,
            content=article.content,
            image_url=article.image_url,
            category=article.category,
            summary_en=article.description or article.title,
            processing_errors=[error],
        )
