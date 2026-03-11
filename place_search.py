from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus


DEFAULT_PLACES_FILE = Path(__file__).resolve().parent / "places.json"


def _load_places(file_path: str | None = None) -> list[dict[str, Any]]:
    target = Path(file_path) if file_path else DEFAULT_PLACES_FILE
    with target.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        return []
    return [p for p in data if isinstance(p, dict)]


def _normalize(s: str | None) -> str:
    return (s or "").strip().lower()


def _build_map_url(place: dict[str, Any]) -> str | None:
    current = place.get("map_url")
    if isinstance(current, str) and current.strip():
        return current.strip()

    lat = place.get("latitude")
    lon = place.get("longitude")
    if isinstance(lat, (float, int)) and isinstance(lon, (float, int)):
        return f"https://www.google.com/maps?q={lat},{lon}"

    address = _normalize(place.get("address"))
    city = _normalize(place.get("city"))
    name = _normalize(place.get("name"))
    if address or city or name:
        query = " ".join(x for x in [name, address, city] if x)
        return "https://www.google.com/maps/search/?api=1&query=" + quote_plus(query)
    return None


def search_places(city: str | None, category: str | None, preferences: list[str]) -> list[dict[str, Any]]:
    city_norm = _normalize(city)
    category_norm = _normalize(category)
    pref_norm = [_normalize(p) for p in preferences if _normalize(p)]

    places = _load_places()
    strict_matches: list[dict[str, Any]] = []

    for place in places:
        place_city = _normalize(place.get("city"))
        place_category = _normalize(place.get("category"))

        city_ok = (not city_norm) or (place_city == city_norm)
        category_ok = (not category_norm) or (place_category == category_norm)
        if city_ok and category_ok:
            strict_matches.append(place)

    if strict_matches:
        return strict_matches

    # Relaxed fallback: keep same city when possible, then category.
    relaxed = [
        p for p in places if (not city_norm or _normalize(p.get("city")) == city_norm)
    ]
    if not relaxed:
        relaxed = [
            p for p in places if (not category_norm or _normalize(p.get("category")) == category_norm)
        ]
    if not relaxed:
        relaxed = places

    if not pref_norm:
        return relaxed

    # Keep places where at least one preference appears in tags or description.
    filtered = []
    for place in relaxed:
        tags = [_normalize(t) for t in place.get("tags", []) if isinstance(t, str)]
        text_blob = " ".join([
            _normalize(place.get("description")),
            _normalize(place.get("address")),
        ])
        if any((pref in tags) or (pref in text_blob) for pref in pref_norm):
            filtered.append(place)
    return filtered or relaxed


def rank_places(results: list[dict[str, Any]], preferences: list[str]) -> list[dict[str, Any]]:
    pref_norm = [_normalize(p) for p in preferences if _normalize(p)]

    def score(place: dict[str, Any]) -> float:
        rating = float(place.get("rating") or 0)
        reviews = int(place.get("reviews_count") or 0)
        tags = [_normalize(t) for t in place.get("tags", []) if isinstance(t, str)]
        desc = _normalize(place.get("description"))
        pref_hits = 0
        for pref in pref_norm:
            if pref in tags or pref in desc:
                pref_hits += 1
        return (rating * 2.0) + (reviews / 200.0) + (pref_hits * 1.5)

    ranked = sorted(results, key=score, reverse=True)
    output: list[dict[str, Any]] = []
    for place in ranked[:10]:
        p = dict(place)
        p["map_url"] = _build_map_url(p)
        output.append(p)
    return output
