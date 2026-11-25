"""Production mock agent. Uvicorn owns SIGTERM and drains requests."""
import json
import logging
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
import redis
from fastapi import Depends, FastAPI, HTTPException, Request
from pydantic import BaseModel, Field
from app.auth import verify_api_key
from app.config import settings
from app.cost_guard import check_budget, record_cost
from app.rate_limiter import check_rate_limit
from app.redis_client import r, redis_healthy
from utils.mock_llm import ask as llm_ask

class JsonFormatter(logging.Formatter):
    def format(self, record):
        entry = {"ts": datetime.now(timezone.utc).isoformat(),
                 "lvl": record.levelname, "event": record.getMessage()}
        entry.update(getattr(record, "fields", {}))
        return json.dumps(entry, ensure_ascii=False)

logger = logging.getLogger("agent")
handler = logging.StreamHandler()
handler.setFormatter(JsonFormatter())
logger.handlers = [handler]
logger.setLevel(logging.INFO)
logger.propagate = False

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("startup", extra={"fields": {"environment": settings.environment}})
    yield
    # Uvicorn waits for in-flight sync endpoints before this cleanup.
    r.close()
    logger.info("shutdown")

app = FastAPI(title="Production AI Agent", lifespan=lifespan)

@app.middleware("http")
async def log_request(request: Request, call_next):
    started = time.perf_counter()
    status = 500
    try:
        response = await call_next(request)
        status = response.status_code
        return response
    finally:
        logger.info("request", extra={"fields": {
            "method": request.method, "path": request.url.path,
            "status": status, "ms": round((time.perf_counter() - started) * 1000, 3)}})

class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)
    user_id: str | None = Field(default=None, max_length=200)

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/ready")
def ready():
    if not redis_healthy():
        raise HTTPException(status_code=503, detail="Redis unavailable")
    return {"ready": True}

@app.post("/ask")
def ask(body: AskRequest, key: str = Depends(verify_api_key)):
    try:
        check_rate_limit(key)
        check_budget()
        answer = llm_ask(body.question)
        # Mock LLM has no tokenizer: estimate usage, not provider billing.
        cost = record_cost(max(1, len(body.question.split())), max(1, len(answer.split())))
    except redis.RedisError:
        logger.warning("redis_unavailable")
        raise HTTPException(status_code=503, detail="Redis unavailable") from None
    return {"question": body.question, "answer": answer, "estimated_cost_usd": cost}
