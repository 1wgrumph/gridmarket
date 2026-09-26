from .contracts import Signal, WorkerStats


class SignalStore:
    def latest(self, report_id: str, zone: str) -> Signal | None:
        return None

    def series(self, report_id: str, zone: str, start: str, end: str) -> list[Signal]:
        return []

    def staleness(self, report_id: str) -> float | None:
        return None


signals = SignalStore()
stats = WorkerStats()


def worker_stats() -> WorkerStats:
    return stats


async def poll() -> None:
    pass
