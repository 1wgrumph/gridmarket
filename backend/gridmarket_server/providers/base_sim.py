from typing import Any


class BaseSim:
    provider_id = "base_sim"
    display_name = "Base Simulation"

    def list_customers(self) -> list[dict[str, Any]]:
        return []

    def list_assets(self) -> list[dict[str, Any]]:
        return []

    def available_capacity(self, asset_id: str, hour: str) -> float:
        return 0.0

    def reserve_capacity(self, tx: Any, asset_id: str, hour: str, kwh: float) -> str:
        raise NotImplementedError

    def release_capacity(self, tx: Any, reservation_id: str) -> None:
        raise NotImplementedError

    def verify_delivery(self, reservation_id: str) -> bool:
        return False

    def asset_status(self, asset_id: str) -> dict[str, Any]:
        return {"online": True}

    def heartbeat(self) -> None:
        pass
