from fastapi import APIRouter

router = APIRouter()
registry: dict[str, object] = {}


@router.get("/v1/market/status")
def status() -> dict[str, str]:
    return {"status": "open"}
