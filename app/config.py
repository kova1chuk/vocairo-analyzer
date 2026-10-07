from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    ANALYZER_API_KEY: str = ""
    DEEPL_API_KEY: str = ""
    CORS_ORIGINS: str = "http://localhost:3000,http://127.0.0.1:3000,http://localhost:3006"
    DEBUG: bool = False
    SENTRY_ENABLED: bool | None = None
    SENTRY_DSN: str = "https://tdAv5w3NahK6wtGrjwDeg1Kh@s2787469.us-west-2a.betterstackdata.com/2787469"
    SENTRY_ENVIRONMENT: str = ""
    SENTRY_RELEASE: str = ""
    MAX_UPLOAD_BYTES: int = 20 * 1024 * 1024
    MAX_EPUB_UNCOMPRESSED_BYTES: int = 100 * 1024 * 1024
    MAX_EPUB_ARCHIVE_ENTRIES: int = 10_000
    MAX_EXTRACTED_TEXT_CHARS: int = 2_000_000
    TRANSLATION_TIMEOUT_SECONDS: float = 8.0
    TRANSLATION_BATCH_TIMEOUT_SECONDS: float = 20.0
    TRANSLATION_BATCH_MAX_ITEMS: int = 100
    TRANSLATION_BATCH_MAX_TOTAL_CHARS: int = 20_000
    TRANSLATION_BATCH_CONCURRENCY: int = 4
    TRANSLATION_PROVIDER_TIMEOUT_SECONDS: float = 3.5
    TRANSLATION_PROVIDER_CONCURRENCY: int = 8

    WORD_FILTER_ENABLED: bool = True
    WORD_FILTER_MIN_WORD_LENGTH: int = 2
    WORD_FILTER_MIN_ZIPF: float = 2.0

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


settings = Settings()
