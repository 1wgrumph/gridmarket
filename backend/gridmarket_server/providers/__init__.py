import os

from .base_sim import BaseSim
from .lonestar import LoneStar

registry = {"base_sim": BaseSim, "lonestar": LoneStar}


def enabled() -> dict[str, type]:
    return {
        name: adapter
        for name, adapter in registry.items()
        if name != "lonestar" or os.getenv("GRIDMARKET_LONESTAR") == "on"
    }
