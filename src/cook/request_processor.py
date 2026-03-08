"""Cook request processor — handles food intelligence queries from Holdsworth."""

from __future__ import annotations

import json
from datetime import datetime, timezone

import structlog
from sqlalchemy import text

from cook.db import get_session
from sturmey.telemetry import extract_trace_context, get_tracer

log = structlog.get_logger(__name__)
_tracer = get_tracer(__name__)

_FOOTMAN = "cook"


async def process_pending_requests() -> None:
    """Pick up pending footman_requests for cook and fulfil them."""
    async with get_session() as session:
        rows = (
            await session.execute(
                text("""
                SELECT id, request_type, payload
                FROM sturmey.footman_requests
                WHERE footman = :footman AND status = 'pending'
                ORDER BY created_at ASC
                LIMIT 5
            """),
                {"footman": _FOOTMAN},
            )
        ).fetchall()

    for row in rows:
        payload = row.payload or {}
        parent_ctx = extract_trace_context(payload)
        with _tracer.start_as_current_span(
            "cook.process_request",
            context=parent_ctx,
            attributes={
                "footman.request_id": str(row.id),
                "footman.request_type": row.request_type,
            },
        ):
            await _handle_request(row.id, row.request_type, payload)


async def _handle_request(request_id, request_type: str, payload: dict) -> None:
    async with get_session() as session:
        await session.execute(
            text("""
                UPDATE sturmey.footman_requests
                SET status = 'processing'
                WHERE id = CAST(:id AS uuid)
            """),
            {"id": str(request_id)},
        )
        await session.commit()

    try:
        result = await _dispatch(request_type, payload)
        status = "complete"
        error = None
    except Exception as exc:
        log.error("cook_request_failed", request_type=request_type, error=str(exc))
        result = None
        status = "failed"
        error = str(exc)

    async with get_session() as session:
        await session.execute(
            text("""
                UPDATE sturmey.footman_requests
                SET status = :status,
                    result = CAST(:result AS jsonb),
                    error = :error,
                    processed_at = :now
                WHERE id = CAST(:id AS uuid)
            """),
            {
                "id": str(request_id),
                "status": status,
                "result": json.dumps(result, default=str) if result is not None else None,
                "error": error,
                "now": datetime.now(timezone.utc),
            },
        )
        await session.commit()

    log.info("cook_request_processed", request_type=request_type, status=status)


async def _dispatch(request_type: str, payload: dict) -> dict:
    from cook.handlers.dietary import (
        handle_get_dietary_profile,
        handle_set_recipe_override,
        handle_update_dietary_profile,
    )
    from cook.handlers.meals import handle_rate_recipe, handle_record_meal
    from cook.handlers.order import handle_order_recipe_ingredients
    from cook.handlers.suggest import handle_check_dietary, handle_suggest_recipes

    handlers = {
        "suggest_recipes": handle_suggest_recipes,
        "check_dietary": handle_check_dietary,
        "get_dietary_profile": handle_get_dietary_profile,
        "update_dietary_profile": handle_update_dietary_profile,
        "record_meal": handle_record_meal,
        "rate_recipe": handle_rate_recipe,
        "order_recipe_ingredients": handle_order_recipe_ingredients,
        "set_recipe_override": handle_set_recipe_override,
    }

    handler = handlers.get(request_type)
    if handler is None:
        raise ValueError(f"Unknown request_type: {request_type}")

    return await handler(payload)
