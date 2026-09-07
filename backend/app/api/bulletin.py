from fastapi import APIRouter

from ..ingest import bulletin

router = APIRouter(prefix="/api", tags=["bulletin"])


@router.get("/bulletin")
def get_latest_bulletin():
    data = bulletin.get_bulletin()
    if data is None:
        return {"available": False, "source": bulletin.SOURCE, "url": bulletin.URL}
    return {"available": True, **data}
