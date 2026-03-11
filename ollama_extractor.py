from __future__ import annotations

import json
import os
import re
from typing import Any
from urllib import error, request

from pydantic import BaseModel, Field, ValidationError


DEEPSEEK_API_URL = os.getenv("DEEPSEEK_API_URL", "https://api.deepseek.com/chat/completions")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "sk-73793626bbc84dc08fd29b886f74b28c")


class QueryExtraction(BaseModel):
    intent: str = "search_places"
    city: str | None = None
    category: str | None = None
    preferences: list[str] = Field(default_factory=list)


OUTPUT_SCHEMA = QueryExtraction.model_json_schema()


SYSTEM_PROMPT = """You are an information extraction engine.
Your job: extract search parameters from a tourism query.
Return ONLY valid JSON matching schema.
Do not return place names.
Do not invent places.
Allowed intent values: search_places, general_question, unsupported.
city must be a city name or null.
category examples: restaurant, cafe, hotel, museum, park.
preferences must be a short list of keywords.
"""


CITY_KEYWORDS = {
    "rabat": "Rabat",
    "casablanca": "Casablanca",
    "marrakech": "Marrakech",
    "fes": "Fes",
    "tanger": "Tanger",
}


CATEGORY_KEYWORDS = {
    "restaurant": "restaurant",
    "restaurants": "restaurant",
    "resto": "restaurant",
    "cafe": "cafe",
    "cafes": "cafe",
    "hotel": "hotel",
    "hotels": "hotel",
    "museum": "museum",
    "musee": "museum",
    "park": "park",
    "parc": "park",
}


PREFERENCE_KEYWORDS = [
    "wifi",
    "calme",
    "quiet",
    "family",
    "famille",
    "romantic",
    "terrace",
    "terrasse",
    "cheap",
    "budget",
    "luxe",
    "luxury",
    "halal",
]


def _extract_content(payload: dict[str, Any]) -> str:
    choices = payload.get("choices")
    if isinstance(choices, list) and choices:
        first = choices[0]
        if isinstance(first, dict):
            message = first.get("message")
            if isinstance(message, dict) and isinstance(message.get("content"), str):
                return message["content"]
    raise ValueError("Missing choices[0].message.content in DeepSeek response")


def _fallback_extract(query: str) -> dict[str, Any]:
    q = query.lower()

    city = None
    for key, value in CITY_KEYWORDS.items():
        if re.search(rf"\b{re.escape(key)}\b", q):
            city = value
            break

    category = None
    for key, value in CATEGORY_KEYWORDS.items():
        if re.search(rf"\b{re.escape(key)}\b", q):
            category = value
            break

    preferences = [p for p in PREFERENCE_KEYWORDS if re.search(rf"\b{re.escape(p)}\b", q)]
    intent = "search_places" if (city or category) else "general_question"

    return QueryExtraction(
        intent=intent,
        city=city,
        category=category,
        preferences=preferences,
    ).model_dump(mode="json")


def extract_query_params_with_ollama(query: str) -> dict[str, Any]:
    if not DEEPSEEK_API_KEY:
        return _fallback_extract(query)

    payload = {
        "model": DEEPSEEK_MODEL,
        "temperature": 0,
        "max_tokens": 180,
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "query_extraction",
                "schema": OUTPUT_SCHEMA,
                "strict": True,
            },
        },
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": query},
        ],
    }

    data = json.dumps(payload).encode("utf-8")
    req = request.Request(
        DEEPSEEK_API_URL,
        data=data,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        },
        method="POST",
    )

    try:
        with request.urlopen(req, timeout=30) as response:
            body = response.read().decode("utf-8")
        content = _extract_content(json.loads(body))
        extracted = QueryExtraction.model_validate_json(content)
        return extracted.model_dump(mode="json")
    except (ValidationError, json.JSONDecodeError, error.URLError, error.HTTPError, ValueError):
        return _fallback_extract(query)
