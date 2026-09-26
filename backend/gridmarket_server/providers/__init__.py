"""Enabled provider classes shared by the market, seed and health loop."""

import os

from .base_sim import BaseSim
from .base_sim import commit_capacity as commit_capacity
from .base_sim import due_capacity as due_capacity
from .base_sim import reserved_capacity as reserved_capacity
from .base_sim import set_delivery_status as set_delivery_status
from .lonestar import LoneStar

registry = {"base_sim": BaseSim, "lonestar": LoneStar}


def enabled() -> dict[str, type[BaseSim]]:
    return {
        name: adapter
        for name, adapter in registry.items()
        if name != "lonestar" or os.getenv("GRIDMARKET_LONESTAR") == "on"
    }
