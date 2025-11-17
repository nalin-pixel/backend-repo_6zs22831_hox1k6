import os
from typing import List, Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from bson.objectid import ObjectId

from database import db, create_document, get_documents
from schemas import Asset, AssetUpdate

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Helpers
class AssetOut(BaseModel):
    id: str
    title: str
    image_url: str
    prompt: str
    is_active: bool


def _serialize_asset(doc) -> AssetOut:
    return AssetOut(
        id=str(doc.get("_id")),
        title=doc.get("title"),
        image_url=doc.get("image_url"),
        prompt=doc.get("prompt"),
        is_active=doc.get("is_active", True),
    )


@app.get("/")
def read_root():
    return {"message": "Assets API running"}


@app.get("/test")
def test_database():
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": [],
    }
    try:
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
            response["database_name"] = db.name
            response["connection_status"] = "Connected"
            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️  Connected but Error: {str(e)[:50]}"
        else:
            response["database"] = "⚠️  Available but not initialized"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:50]}"
    return response


# Seed endpoint: ensure some demo assets exist
@app.post("/api/assets/seed", response_model=List[AssetOut])
def seed_assets():
    if db is None:
        raise HTTPException(status_code=500, detail="Database not available")
    existing = list(db["asset"].find({}).limit(1))
    if existing:
        return [_serialize_asset(doc) for doc in db["asset"].find({}).limit(24)]

    demo = [
        {
            "title": f"Sample #{i+1}",
            "image_url": "https://images.unsplash.com/photo-1518779578993-ec3579fee39f?w=800&q=80&auto=format&fit=crop",
            "prompt": "A futuristic UI with glowing panels and soft gradients",
            "is_active": True,
        }
        for i in range(8)
    ]
    for d in demo:
        create_document("asset", d)
    return [_serialize_asset(doc) for doc in db["asset"].find({}).limit(24)]


@app.get("/api/assets", response_model=List[AssetOut])
def list_assets():
    if db is None:
        raise HTTPException(status_code=500, detail="Database not available")
    docs = get_documents("asset", {}, 100)
    return [_serialize_asset(doc) for doc in docs]


@app.post("/api/assets", response_model=AssetOut)
def create_asset(asset: Asset):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not available")
    inserted_id = create_document("asset", asset)
    doc = db["asset"].find_one({"_id": ObjectId(inserted_id)})
    return _serialize_asset(doc)


@app.patch("/api/assets/{asset_id}", response_model=AssetOut)
def update_asset(asset_id: str, patch: AssetUpdate):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not available")
    try:
        oid = ObjectId(asset_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid asset id")

    update_data = {k: v for k, v in patch.model_dump(exclude_unset=True).items() if v is not None}
    if not update_data:
        raise HTTPException(status_code=400, detail="No changes provided")

    update_data["updated_at"] = __import__("datetime").datetime.utcnow()
    res = db["asset"].find_one_and_update({"_id": oid}, {"$set": update_data}, return_document=True)
    doc = db["asset"].find_one({"_id": oid})
    if not doc:
        raise HTTPException(status_code=404, detail="Asset not found")
    return _serialize_asset(doc)


@app.delete("/api/assets/{asset_id}")
def delete_asset(asset_id: str):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not available")
    try:
        oid = ObjectId(asset_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid asset id")
    db["asset"].delete_one({"_id": oid})
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
