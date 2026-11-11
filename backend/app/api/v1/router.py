from fastapi import APIRouter

from app.api.v1 import comparisons, gtfs, meta, trips

api_router = APIRouter()
api_router.include_router(meta.router)
api_router.include_router(trips.router)
api_router.include_router(comparisons.router)
api_router.include_router(gtfs.router)
