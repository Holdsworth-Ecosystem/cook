"""Meal history and recipe rating handlers."""

from __future__ import annotations

from sqlalchemy import text

from cook.db import get_session


async def handle_record_meal(payload: dict) -> dict:
    """Record a meal that was served."""
    recipe_name = payload.get("recipe_name")
    diner_names = payload.get("diners", [])
    recipe_id = payload.get("recipe_id")

    if not recipe_name:
        raise ValueError("recipe_name is required")
    if not diner_names:
        raise ValueError("At least one diner name is required")

    # Resolve diner IDs
    diner_ids = []
    async with get_session() as session:
        for name in diner_names:
            row = (
                await session.execute(
                    text(
                        "SELECT id FROM sturmey.household_members WHERE LOWER(name) = LOWER(:name)"
                    ),
                    {"name": name},
                )
            ).fetchone()
            if row:
                diner_ids.append(str(row.id))

    if not diner_ids:
        return {
            "success": False,
            "message": f"No household members found matching: {', '.join(diner_names)}",
        }

    # If recipe_id not provided, try to find by name
    if not recipe_id:
        async with get_session() as session:
            row = (
                await session.execute(
                    text(
                        "SELECT id FROM holdsworth.recipes WHERE LOWER(name) = LOWER(:name) LIMIT 1"
                    ),
                    {"name": recipe_name},
                )
            ).fetchone()
            if row:
                recipe_id = str(row.id)

    notes = payload.get("notes")

    async with get_session() as session:
        await session.execute(
            text("""
                INSERT INTO cook.meal_history (recipe_id, recipe_name, diners, notes)
                VALUES (CAST(:recipe_id AS uuid), :recipe_name, CAST(:diners AS uuid[]), :notes)
            """),
            {
                "recipe_id": recipe_id,
                "recipe_name": recipe_name,
                "diners": diner_ids,
                "notes": notes,
            },
        )
        await session.commit()

    return {
        "success": True,
        "message": f"Meal recorded: {recipe_name} for {', '.join(diner_names)}.",
    }


async def handle_rate_recipe(payload: dict) -> dict:
    """Record a recipe rating from a household member."""
    recipe_name = payload.get("recipe_name")
    member_name = payload.get("member_name")
    rating = payload.get("rating")

    if not all([recipe_name, member_name, rating]):
        raise ValueError("recipe_name, member_name, and rating are required")

    try:
        rating = int(rating)
    except (TypeError, ValueError):
        raise ValueError("rating must be an integer")

    if not (1 <= rating <= 5):
        raise ValueError("rating must be between 1 and 5")

    comment = payload.get("comment")

    # Resolve member
    async with get_session() as session:
        member_row = (
            await session.execute(
                text("SELECT id FROM sturmey.household_members WHERE LOWER(name) = LOWER(:name)"),
                {"name": member_name},
            )
        ).fetchone()

    if not member_row:
        return {"success": False, "message": f"No household member found: {member_name}"}

    member_id = str(member_row.id)

    # Find recipe
    recipe_id = payload.get("recipe_id")
    if not recipe_id:
        async with get_session() as session:
            row = (
                await session.execute(
                    text(
                        "SELECT id FROM holdsworth.recipes WHERE LOWER(name) = LOWER(:name) LIMIT 1"
                    ),
                    {"name": recipe_name},
                )
            ).fetchone()
            if row:
                recipe_id = str(row.id)

    # Find most recent meal for this recipe (to link rating to meal)
    meal_id = None
    if recipe_id:
        async with get_session() as session:
            meal_row = (
                await session.execute(
                    text("""
                        SELECT id FROM cook.meal_history
                        WHERE recipe_id = CAST(:recipe_id AS uuid)
                        ORDER BY served_at DESC
                        LIMIT 1
                    """),
                    {"recipe_id": recipe_id},
                )
            ).fetchone()
            if meal_row:
                meal_id = str(meal_row.id)

    async with get_session() as session:
        if meal_id:
            # Upsert on (meal_id, member_id)
            await session.execute(
                text("""
                    INSERT INTO cook.recipe_ratings (recipe_id, meal_id, member_id, rating, comment)
                    VALUES (CAST(:recipe_id AS uuid), CAST(:meal_id AS uuid),
                            CAST(:member_id AS uuid), :rating, :comment)
                    ON CONFLICT (meal_id, member_id)
                    DO UPDATE SET rating = :rating, comment = :comment
                """),
                {
                    "recipe_id": recipe_id,
                    "meal_id": meal_id,
                    "member_id": member_id,
                    "rating": rating,
                    "comment": comment,
                },
            )
        else:
            # No meal to link — insert without meal_id
            await session.execute(
                text("""
                    INSERT INTO cook.recipe_ratings (recipe_id, member_id, rating, comment)
                    VALUES (CAST(:recipe_id AS uuid), CAST(:member_id AS uuid), :rating, :comment)
                """),
                {
                    "recipe_id": recipe_id,
                    "member_id": member_id,
                    "rating": rating,
                    "comment": comment,
                },
            )
        await session.commit()

    return {
        "success": True,
        "message": f"Rating recorded: {member_name} rated {recipe_name} {rating}/5.",
    }
