import logging
from pathlib import Path
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from parade.api.context import AppContext

logger = logging.getLogger(__name__)


def create_app(ctx: AppContext) -> FastAPI:
    app = FastAPI(title="Parade Show Control", version="0.1.0")
    app.state.ctx = ctx

    from parade.api.routes import dashboard, dmx, simulation, routines, setup
    from parade.api.routes.dependencies import get_ctx  # noqa: F401

    app.include_router(dashboard.router)
    app.include_router(dmx.router)
    app.include_router(simulation.router)
    app.include_router(routines.router)
    app.include_router(setup.router)

    static_dir = Path(__file__).parent / "static"
    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=static_dir), name="static")

        @app.get("/")
        async def index():
            return FileResponse(static_dir / "index.html")

    return app
