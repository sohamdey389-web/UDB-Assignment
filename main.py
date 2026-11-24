
import os
import math
import time
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from pymongo import ReturnDocument
from database import token_buckets

app = FastAPI(title="FD Rate Limiter API")

CAPACITY = int(os.getenv("RATE_LIMIT", "5"))
REFILL_RATE = 1.0  # Tokens added per second
RECORD_TTL_SECONDS = 3600


def check_rate_limit(client_id: str) -> dict:
    now = time.time()
    now_ms = int(now * 1000)

    expires_at = datetime.now(timezone.utc) + timedelta(
        seconds=RECORD_TTL_SECONDS
    )

    updated = token_buckets.find_one_and_update(
        {"_id": client_id},
        [
            {
                "$set": {
                    "_refilled": {
                        "$min": [
                            CAPACITY,
                            {
                                "$add": [
                                    {"$ifNull": ["$tokens", CAPACITY]},
                                    {
                                        "$multiply": [
                                            {
                                                "$divide": [
                                                    {
                                                        "$max": [
                                                            0,
                                                            {
                                                                "$subtract": [
                                                                    now_ms,
                                                                    {
                                                                        "$ifNull": [
                                                                            "$last_refill_ms",
                                                                            now_ms,
                                                                        ]
                                                                    },
                                                                ]
                                                            },
                                                        ]
                                                    },
                                                    1000,
                                                ]
                                            },
                                            REFILL_RATE,
                                        ]
                                    },
                                ]
                            },
                        ]
                    }
                }
            },
            {
                "$set": {
                    "allowed": {"$gte": ["$_refilled", 1]},
                    "tokens": {
                        "$cond": [
                            {"$gte": ["$_refilled", 1]},
                            {"$subtract": ["$_refilled", 1]},
                            "$_refilled",
                        ]
                    },
                    "last_refill_ms": now_ms,
                    "expires_at": expires_at,
                }
            },
            {"$unset": "_refilled"},
        ],
        upsert=True,
        return_document=ReturnDocument.AFTER,
    )

    remaining = max(0, math.floor(updated["tokens"]))

    retry_after = max(
        1,
        math.ceil((1 - updated["tokens"]) / REFILL_RATE),
    )

    return {
        "allowed": updated["allowed"],
        "remaining": remaining,
        "retry_after": retry_after,
    }


@app.get("/health")
def health():
    return {"status": "ok", "message": "Rate limiter API is running"}


@app.get("/")
def home():
    return {
        "project": "FD Rate Limiter",
        "algorithm": "Token Bucket",
        "limit": CAPACITY,
        "refill_rate": REFILL_RATE,
        "docs": "/docs",
    }


@app.get("/limited")
def limited():
    # This endpoint is handled by the middleware below.
    return {"message": "Request allowed!", "status": 200}


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    # Keep health checks and documentation accessible.
    exempt_paths = {"/", "/health", "/docs", "/openapi.json", "/redoc"}

    if request.url.path in exempt_paths:
        return await call_next(request)

    client_id = (
        request.headers.get("X-Client-ID")
        or (request.client.host if request.client else "unknown")
    )

    try:
        result = check_rate_limit(client_id)
    except Exception:
        # Do not accidentally allow unlimited requests on DB failure.
        return JSONResponse(
            status_code=503,
            content={"detail": "Rate limiter database unavailable"},
        )

    headers = {
        "X-RateLimit-Limit": str(CAPACITY),
        "X-RateLimit-Remaining": str(result["remaining"]),
    }

    if not result["allowed"]:
        headers["Retry-After"] = str(result["retry_after"])

        return JSONResponse(
            status_code=429,
            content={
                "detail": "Too many requests. Please try again later.",
                "retry_after": result["retry_after"],
            },
            headers=headers,
        )

    response = await call_next(request)

    for name, value in headers.items():
        response.headers[name] = value

    return response
