import json
import logging
import re

import anthropic

from config.settings import Config
from src.ai_processor import ProcessedArticle
from src.utils import retry_with_backoff

logger = logging.getLogger("translator")

TRANSLATION_PROMPT = """You are a professional translator specializing in Indian languages. Translate the following agriculture news content into ALL of these languages: {lang_list}.

Title (English): {title}
Summary (English): {summary}
Key Points (English): {key_points}

Return ONLY valid JSON in this exact structure (use ISO language codes as keys):
{{
  "hi": {{"title": "...", "summary": "...", "key_points": ["...", "...", "..."]}},
  "mr": {{"title": "...", "summary": "...", "key_points": ["...", "...", "..."]}},
  "bn": {{"title": "...", "summary": "...", "key_points": ["...", "...", "..."]}},
  ...
}}

Rules:
- Translate naturally and idiomatically for farmers in each region
- Keep agriculture technical terms accurate
- Use proper Unicode scripts for each language
- Return ONLY the JSON object, no explanation
"""


def _extract_json(text: str) -> dict:
    text = text.strip()
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if match:
        text = match.group(1)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1:
            try:
                return json.loads(text[start:end+1])
            except json.JSONDecodeError:
                pass
    return {}


class Translator:
    def __init__(self, config: Config):
        self.client = anthropic.Anthropic(api_key=config.anthropic_api_key)
        self.model = config.claude_model
        self.config = config
        # Target languages (excluding English since it's already in summary_en)
        self.target_langs = [l for l in config.newsletter_languages if l != "en"]
        self.lang_names = config.LANGUAGE_NAMES

    def translate_articles(self, articles: list) -> list:
        if not self.target_langs:
            logger.info("No non-English languages configured — skipping translation")
            return articles

        total = len(articles)
        for i, article in enumerate(articles, 1):
            logger.info(f"Translating article {i}/{total}: {article.title[:50]}...")
            try:
                article.translations = self._translate_single(article)
            except Exception as e:
                logger.error(f"Translation failed for '{article.title[:40]}': {e}")
                article.processing_errors.append(f"translation_error: {e}")
        return articles

    @retry_with_backoff(max_retries=3, base_delay=3.0)
    def _translate_single(self, article: ProcessedArticle) -> dict:
        lang_list = ", ".join(
            f"{self.lang_names.get(l, l)} ({l})" for l in self.target_langs
        )
        key_points_str = "\n".join(f"- {p}" for p in article.key_points)

        prompt = TRANSLATION_PROMPT.format(
            lang_list=lang_list,
            title=article.title,
            summary=article.summary_en,
            key_points=key_points_str,
        )

        response = self.client.messages.create(
            model=self.model,
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}]
        )
        raw_text = response.content[0].text
        data = _extract_json(raw_text)

        translations = {}
        for lang_code in self.target_langs:
            if lang_code in data:
                t = data[lang_code]
                translations[lang_code] = {
                    "title": t.get("title", article.title),
                    "summary": t.get("summary", article.summary_en),
                    "key_points": t.get("key_points", article.key_points),
                    "language_name": self.lang_names.get(lang_code, lang_code),
                }
            else:
                # Fallback to English
                translations[lang_code] = {
                    "title": article.title,
                    "summary": article.summary_en,
                    "key_points": article.key_points,
                    "language_name": self.lang_names.get(lang_code, lang_code),
                }
        return translations
