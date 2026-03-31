import os
from dataclasses import dataclass, field
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()


@dataclass
class Config:
    anthropic_api_key: str
    claude_model: str
    newsapi_key: str
    newsapi_max_articles: int
    newsletter_languages: list
    news_query: str
    output_dir: Path
    log_level: str
    gmail_recipient: str

    LANGUAGE_NAMES: dict = field(default_factory=lambda: {
        "en": "English",
        "hi": "हिंदी",
        "mr": "मराठी",
        "bn": "বাংলা",
        "te": "తెలుగు",
        "ta": "தமிழ்",
        "gu": "ગુજરાતી",
        "kn": "ಕನ್ನಡ",
        "ml": "മലയാളം",
        "pa": "ਪੰਜਾਬੀ",
        "or": "ଓଡ଼ିଆ",
    })


def load_config() -> Config:
    anthropic_key = os.getenv("ANTHROPIC_API_KEY", "")
    newsapi_key = os.getenv("NEWSAPI_KEY", "")

    if not anthropic_key:
        raise ValueError("ANTHROPIC_API_KEY is required in .env file")

    languages_raw = os.getenv("NEWSLETTER_LANGUAGES", "en,hi")
    languages = [lang.strip() for lang in languages_raw.split(",") if lang.strip()]
    if "en" not in languages:
        languages.insert(0, "en")

    output_dir = Path(os.getenv("OUTPUT_DIR", "./output"))
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "newsletters").mkdir(exist_ok=True)
    (output_dir / "excel").mkdir(exist_ok=True)
    Path("./logs").mkdir(exist_ok=True)

    return Config(
        anthropic_api_key=anthropic_key,
        claude_model=os.getenv("CLAUDE_MODEL", "claude-sonnet-4-6"),
        newsapi_key=newsapi_key,
        newsapi_max_articles=int(os.getenv("NEWSAPI_MAX_ARTICLES", "30")),
        newsletter_languages=languages,
        news_query=os.getenv(
            "NEWS_QUERY",
            "agriculture OR farming OR crop OR kisan OR MSP"
        ),
        output_dir=output_dir,
        log_level=os.getenv("LOG_LEVEL", "INFO"),
        gmail_recipient=os.getenv("GMAIL_RECIPIENT", ""),
    )
