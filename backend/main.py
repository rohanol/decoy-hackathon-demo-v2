"""DeceptionGraph SOC backend. Loopback only.

Run from dg-soc/:  python -m backend.main
"""
import asyncio
import json
import logging
import os
from contextlib import asynccontextmanager
from typing import Literal, Optional

from fastapi import FastAPI, HTTPException, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, ValidationError, field_validator
from starlette.concurrency import run_in_threadpool
from starlette.exceptions import HTTPException as StarletteHTTPException

from .db import Database
from .integrations import Integrations
from .models import IngestEvent, reason_for

HOST = "127.0.0.1"  # never bind anything else (AGENTS.md section 6)
PORT = 8000
MAX_BATCH = 100
MAX_BODY_BYTES = 1024 * 1024
LAB_NOTE = "Simulated lab data from DeceptionGraph SOC decoys. No real systems, people or credentials."
# The Vite dev server (M1). Override with DG_CORS_ORIGINS="http://a,http://b".
DEFAULT_ORIGINS = "http://127.0.0.1:5173,http://localhost:5173"
ERROR_CODES = {400: "bad_request", 404: "not_found", 405: "method_not_allowed",
               413: "too_large", 415: "unsupported_media_type"}

log = logging.getLogger("dg.backend")


class Broadcaster:
    def __init__(self) -> None:
        self.clients: set[WebSocket] = set()

    async def send(self, message: dict) -> None:
        for ws in list(self.clients):
            try:
                await ws.send_json(message)
            except Exception:
                self.clients.discard(ws)


class LinkDecision(BaseModel):
    decision: Literal["confirm", "reject"]
    rationale: str = Field(min_length=5, max_length=1000)

    @field_validator("rationale", mode="before")
    @classmethod
    def _strip(cls, v):
        return v.strip() if isinstance(v, str) else v


def _error(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": {"code": code, "message": message}})


async def _read_capped(request: Request) -> bytes:
    """Read the body but stop as soon as it passes MAX_BODY_BYTES."""
    declared = request.headers.get("content-length")
    if declared and declared.isdigit() and int(declared) > MAX_BODY_BYTES:
        raise HTTPException(413, "body larger than 1 MiB")
    chunks, size = [], 0
    async for chunk in request.stream():
        size += len(chunk)
        if size > MAX_BODY_BYTES:
            raise HTTPException(413, "body larger than 1 MiB")
        chunks.append(chunk)
    return b"".join(chunks)


def create_app(db_path: Optional[str] = None) -> FastAPI:
    db = Database(db_path)
    hub = Broadcaster()
    hooks = Integrations()
    origins = [o.strip() for o in os.environ.get("DG_CORS_ORIGINS", DEFAULT_ORIGINS).split(",") if o.strip()]
    # Writes and their WebSocket messages go out one request at a time, so clients see seq in order.
    write_order = asyncio.Lock()

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        yield
        db.close()

    app = FastAPI(title="DeceptionGraph SOC", version="1.0", lifespan=lifespan)
    app.state.db = db
    app.state.hooks = hooks
    app.add_middleware(CORSMiddleware, allow_origins=origins, allow_methods=["GET", "POST"],
                       allow_headers=["Content-Type"])

    @app.exception_handler(StarletteHTTPException)
    async def _http(_: Request, exc: StarletteHTTPException):
        return _error(exc.status_code, ERROR_CODES.get(exc.status_code, "error"), str(exc.detail))

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError):
        err = exc.errors()[0]
        loc = ".".join(str(p) for p in err["loc"] if p not in ("query", "body", "path"))
        return _error(400, "bad_request", f"{loc}: {err['msg']}")

    @app.exception_handler(Exception)
    async def _crash(_: Request, exc: Exception):
        log.exception("unhandled error")
        return _error(500, "internal_error", "unexpected server error; see the backend log")

    def require_incident(incident_id: str) -> None:
        if not db.incident_exists(incident_id):
            raise HTTPException(404, f"incident {incident_id} not found")

    def full_incident(incident_id: str) -> dict:
        inc = db.incident_detail(incident_id)
        inc["summary"] = hooks.summary(inc)
        inc["active_block"] = hooks.active_block(inc["src_ip"])
        return inc

    async def publish(findings: list, links: list, incidents: list) -> None:
        seq = await run_in_threadpool(db.max_seq)
        for f in findings:
            await hub.send({"seq": seq, "type": "finding", "data": f})
        for l in links:
            await hub.send({"seq": seq, "type": "link", "data": db.public_link(l)})
        for inc_id in incidents:
            summary = await run_in_threadpool(db.incident_summary, inc_id)
            await hub.send({"seq": seq, "type": "incident", "data": summary})

    # ---- ingest ----
    @app.post("/api/ingest/events")
    async def ingest(request: Request):
        # JSON only: a browser page cannot send this content type without a CORS preflight.
        if not request.headers.get("content-type", "").lower().startswith("application/json"):
            raise HTTPException(415, "Content-Type must be application/json")
        raw = await _read_capped(request)
        try:
            body = json.loads(raw)
        except ValueError:
            raise HTTPException(400, "body is not valid JSON")
        items = body.get("events") if isinstance(body, dict) else None
        if not isinstance(items, list):
            raise HTTPException(400, 'body must be {"events": [...]}')
        if len(items) > MAX_BATCH:
            raise HTTPException(413, f"more than {MAX_BATCH} events in one request")

        valid: list[IngestEvent] = []
        rejected: list[dict] = []
        for i, item in enumerate(items):
            try:
                valid.append(IngestEvent.model_validate(item))
            except ValidationError as e:
                rejected.append({"index": i, "reason": reason_for(e)})

        async with write_order:
            result = await run_in_threadpool(db.ingest, valid)  # commits; everything below runs after it
            accepted = [s for s in result["stored"] if s is not None]
            for ev in accepted:
                await hub.send({"seq": ev["seq"], "type": "event", "data": ev})
            await publish(result["findings"], result["links"], result["incidents"])
            for ev in accepted:
                await hooks.on_event(ev)
        return {"accepted": len(accepted), "duplicates": len(result["stored"]) - len(accepted),
                "rejected": rejected}

    # ---- reads ----
    @app.get("/api/events")
    def events(incident_id: Optional[str] = Query(None, max_length=64),
               sensor_id: Optional[str] = Query(None, max_length=64),
               since_seq: int = Query(0, ge=0), limit: int = Query(200, ge=1, le=1000)):
        return db.list_events(incident_id, sensor_id, since_seq, limit)

    @app.get("/api/incidents")
    def incidents():
        return {"items": db.list_incidents()}

    @app.get("/api/incidents/{incident_id}")
    def incident(incident_id: str):
        require_incident(incident_id)
        return full_incident(incident_id)

    @app.get("/api/incidents/{incident_id}/transcript")
    def transcript(incident_id: str, session_id: Optional[str] = Query(None, max_length=128)):
        require_incident(incident_id)
        out = db.transcript(incident_id, session_id)
        if out is None:
            raise HTTPException(404, f"session {session_id} not found in {incident_id}")
        return out

    @app.get("/api/incidents/{incident_id}/export")
    def export(incident_id: str):
        require_incident(incident_id)
        body = full_incident(incident_id)
        body["events"] = db.export_events(incident_id)
        body["note"] = LAB_NOTE
        return JSONResponse(body, headers={
            "Content-Disposition": f'attachment; filename="{incident_id}.json"'})

    @app.get("/api/links")
    def links():
        return {"items": db.list_links()}

    @app.post("/api/links/{link_id}/decision")
    async def decide(link_id: str, body: LinkDecision):
        async with write_order:
            result = await run_in_threadpool(db.decide_link, link_id, body.decision, body.rationale)
            if result is None:
                raise HTTPException(404, f"link {link_id} not found")
            link = db.public_link(result["link"])
            await hub.send({"seq": await run_in_threadpool(db.max_seq), "type": "link", "data": link})
            await publish(result["findings"], [], result["incidents"])
        return link

    @app.get("/api/stats/overview")
    def stats():
        return db.stats()

    @app.get("/api/health")
    def health():
        return {"ok": True, "sensors": db.sensor_last_seen()}

    @app.websocket("/ws/events")
    async def ws_events(ws: WebSocket):
        # Browsers send Origin on WebSockets and CORS does not apply, so check it here.
        origin = ws.headers.get("origin")
        if origin and origin not in origins:
            await ws.close(code=1008)
            return
        await ws.accept()
        hub.clients.add(ws)
        try:
            while True:
                await ws.receive_text()  # server-push only; ignore client chatter
        except WebSocketDisconnect:
            pass
        finally:
            hub.clients.discard(ws)

    hooks.mount(app)
    return app


_app: Optional[FastAPI] = None


def __getattr__(name: str):
    """`backend.main:app` still works for uvicorn, but importing this module (tests,
    tools) no longer creates the default database as a side effect."""
    global _app
    if name == "app":
        if _app is None:
            _app = create_app()
        return _app
    raise AttributeError(name)


if __name__ == "__main__":
    import uvicorn
    logging.basicConfig(level=logging.INFO)
    uvicorn.run("backend.main:create_app", factory=True, host=HOST, port=PORT)
