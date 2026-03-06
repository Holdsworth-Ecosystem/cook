"""Recipe suggestion and dietary checking handlers."""

from __future__ import annotations

from sqlalchemy import text

from cook.db import get_session
from cook.scoring import score_recipe


async def _resolve_member_ids(names: list[str]) -> list[dict]:
    """Resolve member names to IDs. Returns list of {id, name} dicts."""
    members = []
    async with get_session() as session:
        for name in names:
            row = (
                await session.execute(
                    text(
                        "SELECT id, name FROM sturmey.household_members WHERE LOWER(name) = LOWER(:name)"
                    ),
                    {"name": name},
                )
            ).fetchone()
            if row:
                members.append({"id": str(row.id), "name": row.name})
    return members


async def _load_dietary_profiles(member_ids: list[str]) -> list[dict]:
    """Load all dietary profiles for a set of member IDs."""
    if not member_ids:
        return []

    async with get_session() as session:
        rows = (
            (
                await session.execute(
                    text("""
                    SELECT dp.item, dp.item_type, dp.severity, dp.reason, hm.name AS member_name
                    FROM cook.dietary_profiles dp
                    JOIN sturmey.household_members hm ON dp.member_id = hm.id
                    WHERE dp.member_id = ANY(CAST(:ids AS uuid[]))
                """),
                    {"ids": member_ids},
                )
            )
            .mappings()
            .fetchall()
        )

    return [dict(r) for r in rows]


async def _load_recipe_ingredients(recipe_id: str) -> list[str]:
    """Load ingredient names for a recipe."""
    async with get_session() as session:
        rows = (
            await session.execute(
                text(
                    "SELECT name FROM holdsworth.recipe_ingredients WHERE recipe_id = CAST(:id AS uuid)"
                ),
                {"id": recipe_id},
            )
        ).fetchall()
    return [r.name for r in rows]


async def _get_average_ratings(recipe_ids: list[str], member_ids: list[str]) -> dict[str, float]:
    """Get average ratings per recipe for these diners."""
    if not recipe_ids or not member_ids:
        return {}

    async with get_session() as session:
        rows = (
            (
                await session.execute(
                    text("""
                    SELECT CAST(recipe_id AS text) AS recipe_id, AVG(rating) AS avg_rating
                    FROM cook.recipe_ratings
                    WHERE CAST(recipe_id AS text) = ANY(:recipe_ids)
                      AND member_id = ANY(CAST(:member_ids AS uuid[]))
                    GROUP BY recipe_id
                """),
                    {"recipe_ids": recipe_ids, "member_ids": member_ids},
                )
            )
            .mappings()
            .fetchall()
        )

    return {str(r["recipe_id"]): float(r["avg_rating"]) for r in rows}


async def handle_suggest_recipes(payload: dict) -> dict:
    """Suggest recipes suitable for the given diners."""
    diner_names = payload.get("diners", [])
    tags_filter = payload.get("tags", [])
    limit = payload.get("limit", 5)

    if not diner_names:
        return {"error": "At least one diner name is required in 'diners' list."}

    # Resolve members
    members = await _resolve_member_ids(diner_names)
    if not members:
        return {"error": f"No household members found matching: {', '.join(diner_names)}"}

    member_ids = [m["id"] for m in members]
    profiles = await _load_dietary_profiles(member_ids)

    # Load recipes (optionally filtered by tags)
    async with get_session() as session:
        if tags_filter:
            # Filter by tags using array overlap
            rows = (
                await session.execute(
                    text("""
                        SELECT id, name, tags, description, prep_time_minutes, cook_time_minutes, servings
                        FROM holdsworth.recipes
                        WHERE tags && CAST(:tags AS text[])
                        ORDER BY name
                        LIMIT 100
                    """),
                    {"tags": tags_filter},
                )
            ).fetchall()
        else:
            rows = (
                await session.execute(
                    text("""
                        SELECT id, name, tags, description, prep_time_minutes, cook_time_minutes, servings
                        FROM holdsworth.recipes
                        ORDER BY name
                        LIMIT 100
                    """),
                )
            ).fetchall()

    if not rows:
        return {"recipes": [], "message": "No recipes found."}

    recipe_ids = [str(r.id) for r in rows]
    ratings = await _get_average_ratings(recipe_ids, member_ids)

    # Score each recipe
    scored = []
    for r in rows:
        rid = str(r.id)
        ingredients = await _load_recipe_ingredients(rid)
        result = score_recipe(
            recipe_name=r.name,
            recipe_tags=list(r.tags) if r.tags else [],
            ingredient_names=ingredients,
            diner_profiles=profiles,
            average_rating=ratings.get(rid),
        )
        scored.append(
            {
                "recipe_id": rid,
                "name": r.name,
                "description": r.description,
                "tags": list(r.tags) if r.tags else [],
                "prep_time": r.prep_time_minutes,
                "cook_time": r.cook_time_minutes,
                "servings": r.servings,
                **result,
            }
        )

    # Sort: non-blocked first (by score desc), then blocked (by score desc)
    scored.sort(key=lambda x: (x["blocked"], -x["score"]))
    top = scored[:limit]

    # Build summary
    lines = [f"Recipe suggestions for {', '.join(m['name'] for m in members)}:"]
    for i, s in enumerate(top, 1):
        status = "BLOCKED" if s["blocked"] else f"score {s['score']}"
        lines.append(f"  {i}. {s['name']} ({status})")
        for w in s["warnings"]:
            lines.append(f"     Warning: {w}")
        for b in s["bonuses"]:
            lines.append(f"     Bonus: {b}")

    return {"recipes": top, "summary": "\n".join(lines)}


async def handle_check_dietary(payload: dict) -> dict:
    """Check dietary suitability of a specific recipe for all household members."""
    recipe_name = payload.get("recipe_name")
    recipe_id = payload.get("recipe_id")

    if not recipe_name and not recipe_id:
        raise ValueError("Either recipe_name or recipe_id is required")

    # Find the recipe
    async with get_session() as session:
        if recipe_id:
            row = (
                await session.execute(
                    text(
                        "SELECT id, name, tags FROM holdsworth.recipes WHERE id = CAST(:id AS uuid)"
                    ),
                    {"id": recipe_id},
                )
            ).fetchone()
        else:
            row = (
                await session.execute(
                    text(
                        "SELECT id, name, tags FROM holdsworth.recipes WHERE LOWER(name) = LOWER(:name) LIMIT 1"
                    ),
                    {"name": recipe_name},
                )
            ).fetchone()

    if not row:
        return {"error": f"Recipe not found: {recipe_name or recipe_id}"}

    rid = str(row.id)
    ingredients = await _load_recipe_ingredients(rid)

    # Load ALL dietary profiles
    async with get_session() as session:
        profile_rows = (
            (
                await session.execute(
                    text("""
                    SELECT dp.item, dp.item_type, dp.severity, dp.reason, hm.name AS member_name
                    FROM cook.dietary_profiles dp
                    JOIN sturmey.household_members hm ON dp.member_id = hm.id
                    ORDER BY hm.name
                """),
                )
            )
            .mappings()
            .fetchall()
        )

    profiles = [dict(r) for r in profile_rows]
    result = score_recipe(
        recipe_name=row.name,
        recipe_tags=list(row.tags) if row.tags else [],
        ingredient_names=ingredients,
        diner_profiles=profiles,
    )

    return {
        "recipe": row.name,
        "ingredients": ingredients,
        **result,
    }
