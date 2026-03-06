"""Dietary profile handlers — get and update member dietary profiles."""

from __future__ import annotations

from sqlalchemy import text

from cook.db import get_session


async def handle_get_dietary_profile(payload: dict) -> dict:
    """Return all dietary entries for a household member."""
    member_name = payload.get("member_name")
    if not member_name:
        raise ValueError("member_name is required")

    async with get_session() as session:
        rows = (
            (
                await session.execute(
                    text("""
                    SELECT dp.item, dp.item_type, dp.severity, dp.reason, dp.notes, dp.source
                    FROM cook.dietary_profiles dp
                    JOIN sturmey.household_members hm ON dp.member_id = hm.id
                    WHERE LOWER(hm.name) = LOWER(:name)
                    ORDER BY dp.severity, dp.item
                """),
                    {"name": member_name},
                )
            )
            .mappings()
            .fetchall()
        )

    if not rows:
        return {
            "member": member_name,
            "profiles": [],
            "message": f"No dietary profiles found for {member_name}.",
        }

    profiles = [dict(r) for r in rows]
    # Build a human-readable summary
    lines = [f"Dietary profile for {member_name}:"]
    for p in profiles:
        line = f"  {p['severity'].upper()}: {p['item']} ({p['item_type']})"
        if p["reason"]:
            line += f" — {p['reason']}"
        if p["notes"]:
            line += f" [{p['notes']}]"
        lines.append(line)

    return {"member": member_name, "profiles": profiles, "summary": "\n".join(lines)}


async def handle_update_dietary_profile(payload: dict) -> dict:
    """Add or update a dietary profile entry for a household member."""
    member_name = payload.get("member_name")
    item = payload.get("item")
    severity = payload.get("severity")

    if not all([member_name, item, severity]):
        raise ValueError("member_name, item, and severity are required")

    severity = severity.lower()
    if severity not in ("cannot", "dislikes", "neutral", "likes", "loves"):
        raise ValueError(
            f"Invalid severity: {severity}. Must be cannot/dislikes/neutral/likes/loves"
        )

    item_type = payload.get("item_type", "ingredient")
    reason = payload.get("reason")
    notes = payload.get("notes")
    source = payload.get("source", "manual")

    async with get_session() as session:
        # Look up member
        member_row = (
            await session.execute(
                text("SELECT id FROM sturmey.household_members WHERE LOWER(name) = LOWER(:name)"),
                {"name": member_name},
            )
        ).fetchone()

        if not member_row:
            return {
                "success": False,
                "message": f"No household member found with name '{member_name}'.",
            }

        member_id = str(member_row.id)

        # Upsert the profile entry
        await session.execute(
            text("""
                INSERT INTO cook.dietary_profiles (member_id, item, item_type, severity, reason, notes, source)
                VALUES (CAST(:member_id AS uuid), :item, :item_type, :severity, :reason, :notes, :source)
                ON CONFLICT (member_id, item, item_type)
                DO UPDATE SET severity = :severity, reason = :reason, notes = :notes,
                             source = :source, updated_at = NOW()
            """),
            {
                "member_id": member_id,
                "item": item.lower(),
                "item_type": item_type,
                "severity": severity,
                "reason": reason,
                "notes": notes,
                "source": source,
            },
        )
        await session.commit()

    return {
        "success": True,
        "message": f"Updated dietary profile for {member_name}: {severity.upper()} {item} ({item_type}).",
    }
