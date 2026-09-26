"""FastAPI composition root for the contract-first skeleton."""

import asyncio
import os
import sqlite3
from contextlib import asynccontextmanager, suppress
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import (
    adversary_api,
    api,
    bots_api,
    decision_router,
    economy,
    ercot,
    health,
    market,
    nws,
    seed,
)
from .providers import enabled

ROOT = Path(__file__).resolve().parents[2]


def create_app() -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        db_path = Path(os.getenv("GRIDMARKET_DB", "/data/gridmarket.db"))
        db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(db_path) as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.executescript((Path(__file__).with_name("schema.sql")).read_text())
            seed.seed(db)
        app.state.providers = enabled()

        async def repeat(seconds: int, fn):
            while True:
                try:
                    result = fn()
                    if asyncio.iscoroutine(result):
                        await result
                except Exception:
                    import logging

                    logging.getLogger(__name__).exception("Scheduled tick failed: %s", fn.__name__)
                await asyncio.sleep(seconds)

        jobs = [
            asyncio.create_task(repeat(60, decision_router.tick)),
            asyncio.create_task(repeat(60, economy.tick)),
            asyncio.create_task(repeat(10, health.tick)),
        ]
        if os.getenv("GRIDMARKET_WORKER_URL"):
            jobs.append(asyncio.create_task(repeat(60, ercot.poll)))
        if os.getenv("GRIDMARKET_NWS") != "off":
            jobs.append(asyncio.create_task(repeat(60, nws.poll)))
        try:
            yield
        finally:
            for job in jobs:
                job.cancel()
            for job in jobs:
                with suppress(asyncio.CancelledError):
                    await job

    app = FastAPI(title="GridMarket", lifespan=lifespan)
    for module in (market, api, bots_api, decision_router, health, adversary_api):
        app.include_router(module.router)
    for url, relative in (("/llms.txt", "docs/llms.txt"), ("/guide.md", "docs/USER_GUIDE.md")):
        path = ROOT / relative
        if path.is_file():
            app.add_api_route(url, lambda path=path: FileResponse(path), methods=["GET"])
    kit = ROOT / "docs/llm"
    if kit.is_dir():
        app.mount("/kit", StaticFiles(directory=kit), name="kit")
    dashboard = ROOT / "dashboard/dist"
    if dashboard.is_dir():
        app.mount("/", StaticFiles(directory=dashboard, html=True), name="dashboard")
    return app


app = create_app()
