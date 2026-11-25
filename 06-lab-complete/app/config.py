"""Configuration from environment; no usable secret default."""
import os
from dataclasses import dataclass, field
from dotenv import load_dotenv

load_dotenv()

@dataclass(frozen=True)
class Settings:
    port: int = int(os.getenv("PORT", "8000"))
    environment: str = os.getenv("ENVIRONMENT", "development")
    agent_api_key: str = field(default=os.getenv("AGENT_API_KEY", ""), repr=False)
    redis_url: str = field(default=os.getenv("REDIS_URL", "redis://localhost:6379/0"), repr=False)
    rate_limit_per_minute: int = int(os.getenv("RATE_LIMIT_PER_MINUTE", "10"))
    daily_budget_usd: float = float(os.getenv("DAILY_BUDGET_USD", "1"))
    monthly_budget_usd: float = float(os.getenv("MONTHLY_BUDGET_USD", "10"))

    def __post_init__(self):
        if not 1 <= self.port <= 65535 or self.rate_limit_per_minute < 1:
            raise ValueError("Invalid port or rate limit")
        if not all(0 <= v < float("inf") for v in (self.daily_budget_usd, self.monthly_budget_usd)):
            raise ValueError("Budgets must be finite and nonnegative")

settings = Settings()
