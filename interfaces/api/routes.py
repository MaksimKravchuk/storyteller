"""HTTP routes for the mobile API.

Route handlers are intentionally thin: parse the body, call the service
layer, translate service exceptions to HTTP status codes.
"""

from __future__ import annotations

from typing import Annotated, AsyncIterator

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse

from interfaces.api import service
from interfaces.api.deps import get_engine_factory, get_session_store
from interfaces.api.engine_factory import EngineFactory
from interfaces.api.schemas import (
    ActionRequest,
    CreateSessionRequest,
    CreateSessionResponse,
    SessionListResponse,
    SessionState,
)
from interfaces.api.sessions import SessionStore
from interfaces.api.streaming import stream_error, stream_narration

router = APIRouter()

StoreDep = Annotated[SessionStore, Depends(get_session_store)]
EngineFactoryDep = Annotated[EngineFactory, Depends(get_engine_factory)]

_SSE_MEDIA_TYPE = "text/event-stream"


@router.get("/healthz", include_in_schema=False)
async def healthz() -> dict[str, str]:
    """Liveness probe — does not consult the engine factory or session store."""
    return {"status": "ok"}


@router.post(
    "/sessions",
    response_model=CreateSessionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_session(
    body: CreateSessionRequest,
    store: StoreDep,
    engine_factory: EngineFactoryDep,
) -> CreateSessionResponse:
    """Start a new story and return its opening scene."""
    entry = await service.create_session(
        body=body,
        store=store,
        engine_factory=engine_factory,
    )
    state, _, _ = entry.engine.assert_running()
    return CreateSessionResponse(
        session_id=entry.session_id,
        setting=entry.setting,
        language=entry.language,
        opening_scene=entry.opening_scene,
        turn_count=state.turn_count,
        created_at=entry.created_at,
    )


@router.post("/sessions/{session_id}/actions")
async def post_action(
    session_id: str,
    body: ActionRequest,
    store: StoreDep,
) -> StreamingResponse:
    """Submit a player action and stream the Narrator output as SSE.

    The engine returns the narration as one finished string; this
    handler chunks it on whitespace and emits one ``event: chunk``
    frame per chunk, then a final ``event: done`` frame with the full
    narration and the new ``turn_count``. A handler-level failure is
    emitted as a single ``event: error`` SSE frame so streaming clients
    don't have to handle two status codes.
    """
    return StreamingResponse(
        _action_event_stream(session_id, body.action, store),
        media_type=_SSE_MEDIA_TYPE,
    )


@router.get("/sessions/{session_id}", response_model=SessionState)
async def get_session(session_id: str, store: StoreDep) -> SessionState:
    """Return the current state of one session."""
    try:
        return service.get_session_state(session_id, store)
    except service.SessionNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        ) from exc


@router.get("/sessions", response_model=SessionListResponse)
async def list_sessions(store: StoreDep) -> SessionListResponse:
    """List every live session."""
    return SessionListResponse(sessions=service.list_sessions(store))


async def _action_event_stream(
    session_id: str,
    action: str,
    store: SessionStore,
) -> AsyncIterator[str]:
    """Run the action and yield SSE frames, surfacing errors as ``event: error``."""
    try:
        entry, narration = await service.process_action(
            session_id=session_id,
            action=action,
            store=store,
        )
    except service.SessionNotFoundError:
        async for frame in stream_error("Session not found"):
            yield frame
        return
    state, _, _ = entry.engine.assert_running()
    async for frame in stream_narration(narration, state.turn_count):
        yield frame
