from __future__ import annotations

import argparse
import json
import os
import re
from typing import Any
from urllib import error, request

from pydantic import BaseModel, Field, ValidationError, field_validator


GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", os.getenv("GOOGLE_API_KEY", "AIzaSyAB0W_hpGtU7Wkdkyxd85r5jvvA6JCGhXY"))
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")


def _fetch_wikipedia_image(place_name: str, city: str = "", country: str = "") -> str | None:
    """Récupère une vraie image depuis Wikipedia pour un lieu."""
    import urllib.parse
    
    # Essayer plusieurs variantes de recherche
    search_terms = [
        place_name,
        f"{place_name} {city}".strip(),
        f"{place_name} {country}".strip(),
    ]
    
    for term in search_terms:
        if not term:
            continue
        
        # Nettoyer le terme de recherche
        term = term.replace(" ", "_")
        encoded = urllib.parse.quote(term)
        
        # API Wikipedia pour récupérer l'image de la page
        url = (
            f"https://en.wikipedia.org/w/api.php?"
            f"action=query&titles={encoded}&prop=pageimages&format=json&pithumbsize=800"
        )
        
        try:
            req = request.Request(url, headers={"User-Agent": "PlaceSearchBot/1.0"})
            with request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            
            pages = data.get("query", {}).get("pages", {})
            for page_id, page_data in pages.items():
                if page_id != "-1":  # Page existe
                    thumb = page_data.get("thumbnail", {}).get("source")
                    if thumb:
                        return thumb
        except Exception:
            continue
    
    return None


class Place(BaseModel):
    name: str
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

    @field_validator("price_level", mode="before")
    @classmethod
    def convert_price_level(cls, v: Any) -> str | None:
        """Convertit price_level en format $, $$, $$$, ou $$$$."""
        if v is None:
            return None
        if isinstance(v, int):
            return "$" * min(max(v, 1), 4)
        if isinstance(v, str):
            v = v.strip()
            if not v or v.lower() in ("none", "null"):
                return None
            if all(c == "$" for c in v):
                return v
            try:
                num = int(v)
                return "$" * min(max(num, 1), 4)
            except ValueError:
                return None
        return None


def _gemini_url(model: str, api_key: str) -> str:
    return f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"


def _extract_text_from_gemini(body: dict[str, Any]) -> str:
    import sys
    candidates = body.get("candidates", [])
    if not candidates:
        raise ValueError("Gemini n'a pas retourne de contenu (candidates vide)")
    content = candidates[0].get("content", {})
    parts = content.get("parts", []) if isinstance(content, dict) else []
    texts = [p.get("text", "") for p in parts if isinstance(p, dict)]
    answer = "\n".join(t for t in texts if isinstance(t, str) and t.strip()).strip()
    if not answer:
        raise ValueError("Format de reponse Gemini invalide (pas de text dans parts)")
    print(f"[DEBUG] Reponse brute Gemini ({len(answer)} chars):\n{answer[:300]}", file=sys.stderr)
    return answer


def _extract_json_array(text: str) -> list[dict[str, Any]]:
    import sys
    cleaned = text.strip()
    
    # Strip markdown code fences
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`").strip()
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:].strip()
    
    # Find JSON array start
    start = cleaned.find("[")
    if start == -1:
        print(f"[DEBUG] Aucun [ trouve ! text={cleaned[:100]}", file=sys.stderr)
        raise ValueError(f"Aucun [ detecte. Text commence par: {cleaned[:50]}")
    
    # Try to find closing ], if not found, try to fix incomplete JSON
    end = cleaned.rfind("]")
    if end == -1 or end <= start:
        print(f"[DEBUG] Aucun ] ferme, tentative de fixer JSON incomplet...", file=sys.stderr)
        # JSON incomplet, essayer de le fixer
        json_str = cleaned[start:]
        # Compter les { et } pour fermer correctement
        open_braces = json_str.count("{")
        close_braces = json_str.count("}")
        open_brackets = json_str.count("[") - 1  # On ne compte pas celui du départ
        close_brackets = json_str.count("]")
        
        # Ajouter les fermetures manquantes
        json_str += "}" * (open_braces - close_braces)
        json_str += "]" * max(0, open_brackets - close_brackets + 1)
        print(f"[DEBUG] JSON recompose: {json_str[:200]}...", file=sys.stderr)
    else:
        json_str = cleaned[start : end + 1]
    
    try:
        parsed = json.loads(json_str)
    except json.JSONDecodeError as e:
        print(f"[DEBUG] JSON decode error apres fix: {e}", file=sys.stderr)
        # Dernier recours: extraire manuellement les objets
        print(f"[DEBUG] Attempt brute force extraction...", file=sys.stderr)
        parsed = _brute_force_json_extract(json_str)
    
    if not isinstance(parsed, list):
        parsed = [parsed] if isinstance(parsed, dict) else []
    return [item for item in parsed if isinstance(item, dict)]


def _brute_force_json_extract(text: str) -> list[dict[str, Any]]:
    """Extrait les objets JSON meme s'ils sont incomplets."""
    import sys
    result = []
    
    # Strategie 1: chercher les {...} complets
    pattern = r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}'
    matches = re.finditer(pattern, text)
    count = 0
    for match in matches:
        try:
            obj = json.loads(match.group())
            if isinstance(obj, dict) and "name" in obj:
                result.append(obj)
                count += 1
        except json.JSONDecodeError:
            pass
    
    print(f"[DEBUG] Brute force: {count} objets extraits", file=sys.stderr)
    if result:
        return result
    
    # Strategie 2: si aucun objet complet, chercher les debuts de {..."}
    print(f"[DEBUG] Fallback: extraction manuelle des debuts", file=sys.stderr)
    lines = text.split("\n")
    current_obj_lines: list[str] = []
    in_object = False
    brace_count = 0
    
    for line in lines:
        if not in_object and "{" in line:
            in_object = True
            brace_count = 0
        
        if in_object:
            current_obj_lines.append(line)
            brace_count += line.count("{") - line.count("}")
            
            if brace_count <= 0:
                obj_text = "\n".join(current_obj_lines)
                try:
                    obj = json.loads(obj_text)
                    if isinstance(obj, dict) and "name" in obj:
                        result.append(obj)
                except json.JSONDecodeError:
                    pass
                current_obj_lines = []
                in_object = False
    
    # Si on a un objet inacheve a la fin, le terminer
    if in_object and current_obj_lines:
        obj_text = "\n".join(current_obj_lines)
        # Essayer de le fermer
        while obj_text.count("{") > obj_text.count("}"):
            obj_text += "}"
        try:
            obj = json.loads(obj_text)
            if isinstance(obj, dict) and "name" in obj:
                result.append(obj)
        except json.JSONDecodeError:
            pass
    
    print(f"[DEBUG] Apres fallback: {len(result)} objets au total", file=sys.stderr)
    return result


def _normalize_places(places: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for item in places:
        try:
            # Assouplir la validation: name est requis, le reste optionnel
            if not isinstance(item.get("name"), str) or not item["name"].strip():
                continue
            
            place = Place.model_validate(item)
            
            # Générer map_url si absent
            if not place.map_url and place.latitude is not None and place.longitude is not None:
                place = place.model_copy(
                    update={"map_url": f"https://maps.google.com/?q={place.latitude},{place.longitude}"}
                )
            
            # Récupérer une vraie image depuis Wikipedia
            real_image = _fetch_wikipedia_image(place.name, place.city, place.country)
            if real_image:
                place = place.model_copy(update={"image_url": real_image})
            
            normalized.append(place.model_dump(mode="json"))
        except ValidationError as e:
            import sys
            print(f"[DEBUG] Validation error pour {item.get('name', 'unknown')}: {e}", file=sys.stderr)
            continue
    return normalized


def ask_gemini(query: str, system_prompt: str | None = None) -> list[dict[str, Any]]:
    if not GEMINI_API_KEY:
        import sys
        print("Erreur: GEMINI_API_KEY non definie. Definis-la avant de lancer le script:", file=sys.stderr)
        print("Exemple PowerShell: $env:GEMINI_API_KEY='TA_CLE'", file=sys.stderr)
        return []

    system_text = system_prompt or (
        "Return ONLY a JSON array of places. No markdown, no text outside JSON. "
        "Each place object must have: name, description, category, address, city, country, "
        "latitude, longitude, rating, reviews_count, price_level, map_url, tags. "
        "Do NOT include image_url - leave it null. "
        "Return 2 to 3 places only. "
        "Use null for unknown values. "
        "Do not write anything before or after the array."
    )

    payload = {
        "systemInstruction": {
            "parts": [{"text": system_text}],
        },
        "contents": [
            {
                "role": "user",
                "parts": [{"text": query}],
            }
        ],
        "generationConfig": {
            "temperature": 0,
            "maxOutputTokens": 3000,
        },
    }

    data = json.dumps(payload).encode("utf-8")
    req = request.Request(
        _gemini_url(GEMINI_MODEL, GEMINI_API_KEY),
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with request.urlopen(req, timeout=60) as resp:
            body = json.loads(resp.read().decode("utf-8"))
        import sys
        print(f"[DEBUG] Body Gemini: {json.dumps(body, indent=2)[:500]}", file=sys.stderr)
        raw_text = _extract_text_from_gemini(body)
        raw_places = _extract_json_array(raw_text)
        result = _normalize_places(raw_places)
        print(f"[DEBUG] Places normalisees: {len(result)}", file=sys.stderr)
        return result
    except (error.HTTPError, error.URLError, json.JSONDecodeError, ValueError) as exc:
        import sys
        print(f"Erreur lors de la requete Gemini: {exc.__class__.__name__}: {exc}", file=sys.stderr)
        return []
    except Exception as exc:
        import sys
        import traceback
        print(f"Erreur inattendue: {exc}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        return []


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("query", help="Question utilisateur")
    args = parser.parse_args()

    result = ask_gemini(args.query)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
