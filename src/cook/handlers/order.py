"""Order recipe ingredients handler — delegates to the Ocado footman."""

from __future__ import annotations

import json
import uuid

from sqlalchemy import text

from cook.db import get_session


async def handle_order_recipe_ingredients(payload: dict) -> dict:
    """Look up recipe ingredients and submit them to the Ocado footman via footman_requests."""
    recipe_name = payload.get("recipe_name")
    recipe_id = payload.get("recipe_id")

    if not recipe_name and not recipe_id:
        raise ValueError("Either recipe_name or recipe_id is required")

    # Find the recipe
    async with get_session() as session:
        if recipe_id:
            row = (
                await session.execute(
                    text("SELECT id, name FROM holdsworth.recipes WHERE id = CAST(:id AS uuid)"),
                    {"id": recipe_id},
                )
            ).fetchone()
        else:
            row = (
                await session.execute(
                    text(
                        "SELECT id, name FROM holdsworth.recipes WHERE LOWER(name) = LOWER(:name) LIMIT 1"
                    ),
                    {"name": recipe_name},
                )
            ).fetchone()

    if not row:
        return {"error": f"Recipe not found: {recipe_name or recipe_id}"}

    # Load ingredients
    async with get_session() as session:
        ingredient_rows = (
            await session.execute(
                text("""
                    SELECT name, quantity, unit, ocado_query
                    FROM holdsworth.recipe_ingredients
                    WHERE recipe_id = CAST(:id AS uuid)
                    ORDER BY sort_order
                """),
                {"id": str(row.id)},
            )
        ).fetchall()

    if not ingredient_rows:
        return {"error": f"No ingredients found for recipe '{row.name}'."}

    # Build items list for smart_order
    items = []
    for ing in ingredient_rows:
        # Use ocado_query if set, otherwise ingredient name
        query = ing.ocado_query or ing.name
        items.append(query)

    # Submit to Ocado footman via footman_requests
    request_id = str(uuid.uuid4())
    async with get_session() as session:
        await session.execute(
            text("""
                INSERT INTO sturmey.footman_requests
                    (id, footman, source_system, request_type, payload)
                VALUES
                    (CAST(:id AS uuid), 'ocado', 'cook', 'smart_order', CAST(:payload AS jsonb))
            """),
            {
                "id": request_id,
                "payload": json.dumps({"items": items}),
            },
        )
        await session.commit()

    return {
        "success": True,
        "message": f"Submitted {len(items)} ingredients from '{row.name}' to the Ocado footman.",
        "items": items,
    }
