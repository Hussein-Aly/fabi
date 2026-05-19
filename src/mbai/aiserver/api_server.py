# ==========================================================================
# Copyright (c) Fabasoft R&D GmbH, A-4020 Linz, 1988-2026.
# (header unchanged)
# ==========================================================================
import logging
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from ag_ui.core import RunAgentInput
from fastapi import APIRouter, Body, Depends, FastAPI, File, Request, UploadFile
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from starlette.responses import FileResponse, Response

from mbai.ai_gateway.service import AIGateway
from mbai.aiserver.agui_glue import handle_agui_request
from mbai.aiserver.api_server_auth import jwt_required
from mbai.aiserver.config import settings
from mbai.aiserver.dependencies import get_gateway
from mbai.telemetry.setup import configure_telemetry

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """App lifespan. Construct shared dependencies once, tear down on exit.

    The AIGateway is built here (eagerly, before any requests) and stored
    on `app.state.gateway`. The `get_gateway` dependency exposes it to
    route handlers through Depends.
    """
    configure_telemetry(app)
    app.state.gateway = AIGateway()
    yield
    # Teardown placeholder. AIGateway is stateless today; if it ever
    # grows resources to close (HTTP clients, DB connections), call
    # `await app.state.gateway.aclose()` here.


app = FastAPI(
    title=settings.fast_api_app_title,
    description=settings.fast_api_app_description,
    docs_url=None,
    redoc_url=None,
    openapi_url="/openapi.json",
    swagger_ui_oauth2_redirect_url=None,
    lifespan=lifespan,
)

# Apply FastAPI auto-instrumentation immediately at construction time.
# Lifespan-timed instrumentation can fail silently in some versions.
FastAPIInstrumentor.instrument_app(app)

THIS_DIR = Path(__file__).parent
THIS_DIR_PROTOTYPE = Path(__file__).parent / "agui_prototype"

if settings.fast_api_docs_enabled:
    logger.info("api docs enabled: load swagger_ui")
    from fastapi_swagger import patch_fastapi
    patch_fastapi(app, redirect_from_root_to_docs=False)
else:
    logger.info("api docs are disabled")

v1_router = APIRouter(
    prefix="/api/v1",
    dependencies=[Depends(jwt_required)] if settings.jwt_enabled else [],
)


# -------------------------------------------------------
# Default routes
# -------------------------------------------------------

@app.get("/health-check", summary="Health Check")
def route_health_check() -> dict:
    return {"status": "ok"}


@app.get("/test_file.txt")
def main_ts() -> FileResponse:
    return FileResponse(THIS_DIR_PROTOTYPE / "static/test_file.txt")


# -------------------------------------------------------
# AG-UI prototype
# -------------------------------------------------------

UPLOAD_DIR = THIS_DIR_PROTOTYPE / "upload"
UPLOAD_DIR.mkdir(exist_ok=True)


@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    file_id = uuid.uuid4().hex[:12]
    suffix = Path(file.filename).suffix if file.filename else ""
    stored_name = f"{file_id}{suffix}"
    dest = UPLOAD_DIR / stored_name
    contents = await file.read()
    dest.write_bytes(contents)
    return {
        "title": file.filename,
        "filename": stored_name,
        "size_bytes": len(contents),
        "content_type": file.content_type,
    }


@app.get("/")
@app.get("/agui")
async def serve_frontend():
    return FileResponse(
        THIS_DIR_PROTOTYPE / "agui/frontend.html",
        media_type="text/html",
    )


@app.post("/agui_agent")
async def run_agent(
    request: Request,
    body: RunAgentInput = Body(...),
    gateway: AIGateway = Depends(get_gateway),
) -> Response:
    return await handle_agui_request(request, body, gateway)


app.include_router(v1_router)


if __name__ == "__main__":
    uvicorn.run(
        "mbai.aiserver.api_server:app",
        host="0.0.0.0",
        port=9001,
        reload=True,
    )