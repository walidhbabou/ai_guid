from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn
import os
import sys
from main import ask_gemini

app = FastAPI(
    title="🌍 AI Place Explorer API",
    version="1.0.0",
    description="API pour explorer les lieux touristiques en JSON"
)

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ===== Models =====
class SearchRequest(BaseModel):
    query: str
    limit: int = 5

class PlaceResponse(BaseModel):
    name: str
    description: str
    category: str
    address: str
    city: str
    country: str
    rating: float | None
    reviews_count: int | None
    price_level: str | None
    map_url: str | None
    tags: list[str]

class SearchResponse(BaseModel):
    success: bool
    count: int
    places: list[PlaceResponse]
    error: str | None = None

# ===== Routes =====
@app.get("/")
async def root():
    """📋 Info API"""
    return {
        "title": "🌍 AI Place Explorer API",
        "version": "1.0.0",
        "status": "✅ Running",
        "endpoints": {
            "health": "GET /health",
            "search": "POST /search",
            "docs": "GET /docs",
            "openapi": "GET /openapi.json"
        }
    }

@app.get("/health")
async def health():
    """✅ Vérifier le statut de l'API"""
    return {
        "status": "🟢 Online",
        "api": "AI Place Explorer",
        "version": "1.0.0"
    }

@app.post("/search", response_model=SearchResponse)
async def search(request: SearchRequest):
    """🔍 Chercher des lieux touristiques
    
    Query: "meilleurs restaurants à Marrakech"
    """
    if not request.query or len(request.query.strip()) < 2:
        raise HTTPException(
            status_code=400,
            detail="Query doit avoir au moins 2 caractères"
        )
    
    try:
        print(f"[API] Recherche: {request.query}", file=sys.stderr)
        places = ask_gemini(request.query)
        
        # Limite les résultats
        places = places[:request.limit]
        
        return SearchResponse(
            success=True,
            count=len(places),
            places=places,
            error=None
        )
    except Exception as e:
        print(f"[API] ❌ Erreur: {e}", file=sys.stderr)
        return SearchResponse(
            success=False,
            count=0,
            places=[],
            error=str(e)
        )

@app.post("/search/batch")
async def search_batch(requests: list[SearchRequest]):
    """🔄 Chercher plusieurs requêtes à la fois"""
    results = []
    for req in requests:
        result = await search(req)
        results.append(result)
    return {"searches": results, "total": len(results)}

@app.get("/search/{query}")
async def search_simple(query: str, limit: int = 5):
    """🔍 Chercher via URL (GET)
    
    Exemple: /search/restaurants%20à%20Paris?limit=3
    """
    request = SearchRequest(query=query, limit=limit)
    return await search(request)

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    debug = os.getenv("DEBUG", "False") == "True"
    
    print(f"🚀 API démarrée sur http://0.0.0.0:{port}", file=sys.stderr)
    print(f"📚 Docs: http://0.0.0.0:{port}/docs", file=sys.stderr)
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=port,
        reload=debug
    )