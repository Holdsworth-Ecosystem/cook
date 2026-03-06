"""Recipe suitability scorer — pure Python, no LLM.

For each recipe + set of diners, checks dietary profiles against recipe
ingredients. Returns a score and any warnings (blocked ingredients, etc.).
"""

from __future__ import annotations

# Ingredient group mappings — if a diner has a profile entry for a group key,
# all members of that group are treated as matching.
INGREDIENT_GROUPS: dict[str, set[str]] = {
    "dairy": {"milk", "cream", "butter", "cheese", "yoghurt", "yogurt", "creme fraiche"},
    "wheat": {"flour", "bread", "pasta", "noodles", "couscous", "breadcrumbs", "pastry"},
    "gluten": {"flour", "bread", "pasta", "noodles", "couscous", "breadcrumbs", "pastry"},
    "shellfish": {"prawn", "prawns", "shrimp", "crab", "lobster", "mussel", "mussels"},
    "nuts": {"almond", "walnut", "cashew", "peanut", "pistachio", "hazelnut", "pecan"},
    "fish": {"salmon", "cod", "tuna", "mackerel", "haddock", "sardine", "anchovy", "trout"},
    "eggs": {"egg", "eggs"},
    "soy": {"soy", "soya", "tofu", "edamame"},
}

# Reverse lookup: ingredient_name -> group keys that contain it
_INGREDIENT_TO_GROUPS: dict[str, set[str]] = {}
for _group, _members in INGREDIENT_GROUPS.items():
    for _member in _members:
        _INGREDIENT_TO_GROUPS.setdefault(_member, set()).add(_group)

SEVERITY_SCORES = {
    "cannot": -1000,  # blocks the recipe entirely
    "dislikes": -20,
    "neutral": 0,
    "likes": 15,
    "loves": 30,
}


def _normalise(s: str) -> str:
    return s.strip().lower()


def _ingredient_matches_profile(ingredient_name: str, profile_item: str, profile_type: str) -> bool:
    """Check if a recipe ingredient matches a dietary profile entry."""
    if profile_type not in ("ingredient", "category"):
        return False

    ing = _normalise(ingredient_name)
    item = _normalise(profile_item)

    # Direct substring match
    if item in ing or ing in item:
        return True

    # Group expansion: if profile item is a group key, check if ingredient is in that group
    group_members = INGREDIENT_GROUPS.get(item)
    if group_members:
        for member in group_members:
            if member in ing:
                return True

    # Reverse: if ingredient is a group member, check if profile item matches the group
    groups_for_ing = _INGREDIENT_TO_GROUPS.get(ing, set())
    if item in groups_for_ing:
        return True

    return False


def _cuisine_matches_profile(recipe_tags: list[str], profile_item: str, profile_type: str) -> bool:
    """Check if recipe tags match a cuisine/category profile entry."""
    if profile_type not in ("cuisine", "category"):
        return False
    item = _normalise(profile_item)
    for tag in recipe_tags:
        if item in _normalise(tag) or _normalise(tag) in item:
            return True
    return False


def _dish_matches_profile(recipe_name: str, profile_item: str, profile_type: str) -> bool:
    """Check if a recipe name matches a dish profile entry."""
    if profile_type != "dish":
        return False
    return _normalise(profile_item) in _normalise(recipe_name)


def score_recipe(
    recipe_name: str,
    recipe_tags: list[str],
    ingredient_names: list[str],
    diner_profiles: list[dict],
    average_rating: float | None = None,
) -> dict:
    """Score a recipe for a set of diners.

    Args:
        recipe_name: Name of the recipe.
        recipe_tags: Tags on the recipe (e.g. ["Thai", "quick"]).
        ingredient_names: List of ingredient names in the recipe.
        diner_profiles: List of dicts, each with keys:
            member_name, item, item_type, severity, reason
        average_rating: Mean rating from previous meals (1-5), or None.

    Returns:
        dict with keys: score, blocked, warnings, bonuses
    """
    score = 100  # base score
    blocked = False
    warnings: list[str] = []
    bonuses: list[str] = []

    for profile in diner_profiles:
        member = profile["member_name"]
        item = profile["item"]
        item_type = profile["item_type"]
        severity = profile["severity"]
        severity_score = SEVERITY_SCORES.get(severity, 0)

        # Check ingredient matches
        for ing_name in ingredient_names:
            if _ingredient_matches_profile(ing_name, item, item_type):
                score += severity_score
                if severity == "cannot":
                    blocked = True
                    reason = f" ({profile.get('reason', '')})" if profile.get("reason") else ""
                    warnings.append(
                        f"{member} cannot eat {item}{reason} — recipe contains {ing_name}"
                    )
                elif severity == "dislikes":
                    warnings.append(f"{member} dislikes {item} — recipe contains {ing_name}")
                elif severity in ("likes", "loves"):
                    bonuses.append(f"{member} {severity} {item}")
                break  # one match per profile entry is enough

        # Check cuisine/tag matches
        if _cuisine_matches_profile(recipe_tags, item, item_type):
            score += severity_score
            if severity == "cannot":
                blocked = True
                warnings.append(f"{member} cannot eat {item} cuisine")
            elif severity == "dislikes":
                warnings.append(f"{member} dislikes {item} cuisine")
            elif severity in ("likes", "loves"):
                bonuses.append(f"{member} {severity} {item}")

        # Check dish name matches
        if _dish_matches_profile(recipe_name, item, item_type):
            score += severity_score
            if severity == "cannot":
                blocked = True
                warnings.append(f"{member} cannot eat {item}")
            elif severity == "dislikes":
                warnings.append(f"{member} dislikes {item}")
            elif severity in ("likes", "loves"):
                bonuses.append(f"{member} {severity} {item}")

    # Factor in past ratings
    if average_rating is not None:
        score += int((average_rating - 3) * 10)  # 5-star = +20, 1-star = -20

    return {
        "score": score,
        "blocked": blocked,
        "warnings": warnings,
        "bonuses": bonuses,
    }
