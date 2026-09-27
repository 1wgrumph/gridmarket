"""DEC-GM-113 amendments 3 and 9: immutable availability and interrupted feeds."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from types import MappingProxyType


def aware(moment):
    if moment.tzinfo is None or moment.utcoffset() is None:
        raise ValueError("Timezone-aware timestamp required")
    return moment


@dataclass(frozen=True)
class Observation:
    series: str
    source: str
    value: Decimal | None
    unit: str
    interval_start: datetime
    interval_end: datetime
    published_at: datetime | None
    available_at: datetime | None
    quality: str
    zone: str
    settlement_point: str | None = None
    retrieval_time: datetime | None = None
    provenance: Mapping = field(default_factory=dict)

    def __post_init__(self):
        for name in (
            "interval_start",
            "interval_end",
            "published_at",
            "available_at",
            "retrieval_time",
        ):
            if getattr(self, name) is not None:
                aware(getattr(self, name))
        if self.interval_end <= self.interval_start:
            raise ValueError("Observation interval must be positive")
        if self.value is not None:
            value = Decimal(str(self.value))
            if not value.is_finite():
                raise ValueError("Observation value must be finite")
            object.__setattr__(self, "value", value)
        # Provenance is retained as immutable descriptive text, not a mutable data channel.
        object.__setattr__(
            self,
            "provenance",
            MappingProxyType({str(key): str(value) for key, value in self.provenance.items()}),
        )


@dataclass(frozen=True)
class FeedWindow:
    source: str
    start: datetime
    end: datetime

    def __post_init__(self):
        if aware(self.end) <= aware(self.start):
            raise ValueError("Feed window must be positive")


@dataclass(frozen=True)
class InformationView:
    decision_time: datetime
    observations: tuple[Observation, ...]


class InformationSet:
    def __init__(self, observations):
        self._observations = tuple(observations)

    def at(self, decision_time, feed_interrupts=()):
        aware(decision_time)
        merged = []
        for window in sorted(feed_interrupts, key=lambda w: (w.source, w.start, w.end)):
            if merged and merged[-1].source == window.source and window.start <= merged[-1].end:
                previous = merged.pop()
                merged.append(
                    FeedWindow(window.source, previous.start, max(previous.end, window.end))
                )
            else:
                merged.append(window)
        active = [w for w in merged if w.start <= decision_time < w.end]
        latest = {}
        for row in self._observations:
            if (
                row.available_at is None
                or row.published_at is None
                or row.available_at > decision_time
                or row.published_at > decision_time
                or row.quality in {"settlement_only", "retrospective", "unavailable"}
            ):
                continue
            windows = [w for w in active if w.source == row.source]
            if any(row.available_at >= w.start for w in windows):
                continue
            if (
                windows
                and row.series != "dam_spp"
                and decision_time - row.interval_end >= timedelta(minutes=30)
            ):
                continue
            key = (
                row.series,
                row.source,
                row.zone,
                row.settlement_point or "",
                row.interval_start,
                row.interval_end,
            )
            previous = latest.get(key)
            version = (row.available_at, row.published_at)
            if previous is None or version > (previous.available_at, previous.published_at):
                latest[key] = row
            elif version == (previous.available_at, previous.published_at) and row != previous:
                raise ValueError("Conflicting observation versions")
        return InformationView(decision_time, tuple(latest[key] for key in sorted(latest)))
