from fastapi import APIRouter

router = APIRouter()


def heartbeat(provider_id: str) -> None:
    pass


def is_online(provider_id: str) -> bool:
    return True


def tick() -> None:
    pass
