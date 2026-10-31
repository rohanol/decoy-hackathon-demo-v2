"""Hooks into teammates' modules, each optional so the backend runs before they land.

- Prajwal (M4): analyst/summarise.py   summarise(incident) -> {"source", "text", "cited_event_ids"}
- Vedant (M2):  response/router.py     router (APIRouter), on_event(event), optional active_block(src_ip)
"""
import importlib
import inspect
import logging

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

log = logging.getLogger("dg.integrations")


def _optional_import(name: str):
    try:
        return importlib.import_module(name)
    except ModuleNotFoundError as e:
        if e.name and (name == e.name or name.startswith(e.name + ".")):
            return None  # module not written yet
        log.exception("%s failed to import", name)  # a real bug inside the teammate's module
        return None
    except Exception:
        log.exception("%s failed to import", name)
        return None


def rule_summary(incident: dict) -> dict:
    """Fallback when analyst.summarise is missing or fails: one sentence per finding."""
    findings = incident.get("findings", [])
    if not findings:
        return {"source": "rules", "text": "No findings yet for this source.", "cited_event_ids": []}
    sentences, cited = [], []
    for f in findings:
        note = " (waits for analyst confirmation)" if f.get("pending_confirmation") else ""
        sentences.append(f"{f['label']}{note}.")
        cited.extend(e for e in f["evidence_event_ids"][:3] if e not in cited)
    return {"source": "rules", "text": " ".join(sentences), "cited_event_ids": cited}


class Integrations:
    def __init__(self) -> None:
        analyst = _optional_import("analyst.summarise")
        self._summarise = getattr(analyst, "summarise", None)
        response = _optional_import("response.router")
        self.response_router = getattr(response, "router", None)
        self._on_event = getattr(response, "on_event", None)
        self._active_block = getattr(response, "active_block", None)

    def summary(self, incident: dict) -> dict:
        if self._summarise:
            try:
                out = self._summarise(incident)
                if isinstance(out, dict) and "text" in out:
                    return out
            except Exception:
                log.exception("analyst.summarise failed; using rule summary")
        return rule_summary(incident)

    def active_block(self, src_ip: str):
        if self._active_block:
            try:
                return self._active_block(src_ip)
            except Exception:
                log.exception("response.active_block failed")
        return None

    async def on_event(self, event: dict) -> None:
        """Called once per newly stored event, after commit. Never breaks ingest."""
        if not self._on_event:
            return
        try:
            if inspect.iscoroutinefunction(self._on_event):
                await self._on_event(event)
            else:
                await run_in_threadpool(self._on_event, event)  # file I/O must not block the event loop
        except Exception:
            log.exception("response.on_event failed for %s", event.get("event_id"))

    def mount(self, app) -> None:
        if self.response_router is not None:
            app.include_router(self.response_router, prefix="/api/response")
            return
        placeholder = APIRouter()

        @placeholder.api_route("/{path:path}", methods=["GET", "POST"])
        async def unavailable(path: str, request: Request):
            return JSONResponse(status_code=503, content={"error": {
                "code": "response_unavailable",
                "message": "response/router.py is not installed yet (owner: M2)"}})

        app.include_router(placeholder, prefix="/api/response")
