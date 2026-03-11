from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class PlaceOut(BaseModel):
    name: str = ""
    description: str = ""
    category: str = ""
    address: str = ""
    city: str = ""
    country: str = ""
    latitude: float | None = None
    longitude: float | None = None
    rating: float | None = None
    reviews_count: int | None = None
    price_level: str | None = None
    image_url: str | None = None
    map_url: str | None = None
    tags: list[str] = Field(default_factory=list)


class FinalResponse(BaseModel):
    query: str
    intent: str
    city: str | None = None
    country: str | None = None
    category_requested: str | None = None
    preferences: list[str] = Field(default_factory=list)
    message: str
    places: list[PlaceOut] = Field(default_factory=list)


def build_json_response(query: str, extracted: dict[str, Any], places: list[dict[str, Any]]) -> dict[str, Any]:
    city = extracted.get("city")
    category = extracted.get("category")
    preferences = extracted.get("preferences") or []
    intent = extracted.get("intent") or "search_places"

    country = None
    if places:
        country = places[0].get("country")

    if places:
        message = f"{len(places)} place(s) found"
    else:
        message = "No matching place found in local database"

    payload = FinalResponse(
        query=query,
        intent=intent,
        city=city,
        country=country,
        category_requested=category,
        preferences=preferences,
        message=message,
        places=places,
    )
    return payload.model_dump(mode="json")
