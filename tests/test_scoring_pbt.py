"""Property-based tests for the recipe suitability scorer.

Uses Hypothesis to verify invariants that must hold for ALL inputs,
not just the examples in test_scoring.py.
"""

from __future__ import annotations

from hypothesis import given, settings, assume
from hypothesis import strategies as st

from cook.scoring import (
    INGREDIENT_GROUPS,
    SEVERITY_SCORES,
    _cuisine_matches_profile,
    _dish_matches_profile,
    _has_unresolved_ingredients,
    _ingredient_matches_profile,
    score_recipe,
)

# ---------------------------------------------------------------------------
# Strategies — reusable input generators
# ---------------------------------------------------------------------------

SEVERITIES = list(SEVERITY_SCORES.keys())
ITEM_TYPES = ["ingredient", "category", "cuisine", "dish"]
GROUP_KEYS = list(INGREDIENT_GROUPS.keys())

# All known group members across all groups
ALL_GROUP_MEMBERS = sorted({member for members in INGREDIENT_GROUPS.values() for member in members})

# Names that won't accidentally substring-match ingredient groups
SAFE_NAMES = st.sampled_from(
    [
        "chicken",
        "beef",
        "carrot",
        "potato",
        "onion",
        "garlic",
        "pepper",
        "tomato",
        "rice",
        "lentil",
        "apple",
        "banana",
    ]
)

st_severity = st.sampled_from(SEVERITIES)
st_item_type = st.sampled_from(ITEM_TYPES)


def st_profile(
    member_name=None,
    severity=None,
    item=None,
    item_type=None,
):
    """Strategy for a single diner profile dict."""
    return st.fixed_dictionaries(
        {
            "member_name": member_name or st.sampled_from(["Dave", "Lisa", "Hannah", "David"]),
            "item": item
            or st.sampled_from(GROUP_KEYS + ALL_GROUP_MEMBERS + ["chicken", "beef", "rice"]),
            "item_type": item_type or st_item_type,
            "severity": severity or st_severity,
            "reason": st.sampled_from(["allergy", "intolerance", "preference", None]),
        }
    )


def st_override(member_name=None, suitability=None):
    """Strategy for a single recipe override dict."""
    return st.fixed_dictionaries(
        {
            "member_name": member_name or st.sampled_from(["Dave", "Lisa", "Hannah", "David"]),
            "suitability": suitability or st_severity,
            "reason": st.sampled_from(["manual correction", "contains hidden wheat", ""]),
        }
    )


# ---------------------------------------------------------------------------
# score_recipe: structural invariants
# ---------------------------------------------------------------------------


class TestScoreRecipeProperties:
    """Properties that must hold for ANY valid input to score_recipe."""

    @given(
        recipe_name=st.text(min_size=1, max_size=50),
        tags=st.lists(st.text(min_size=1, max_size=20), max_size=5),
        ingredients=st.lists(SAFE_NAMES, max_size=10),
        profiles=st.lists(st_profile(), max_size=6),
        rating=st.one_of(st.none(), st.floats(min_value=1.0, max_value=5.0)),
    )
    @settings(max_examples=300)
    def test_result_has_required_keys(self, recipe_name, tags, ingredients, profiles, rating):
        """score_recipe always returns a dict with score, blocked, warnings, bonuses."""
        result = score_recipe(recipe_name, tags, ingredients, profiles, rating)
        assert isinstance(result, dict)
        assert "score" in result
        assert "blocked" in result
        assert "warnings" in result
        assert "bonuses" in result
        assert isinstance(result["score"], int)
        assert isinstance(result["blocked"], bool)
        assert isinstance(result["warnings"], list)
        assert isinstance(result["bonuses"], list)

    @given(
        ingredients=st.lists(SAFE_NAMES, max_size=10),
        profiles=st.lists(st_profile(), max_size=6),
    )
    @settings(max_examples=200)
    def test_blocked_implies_warning(self, ingredients, profiles):
        """If a recipe is blocked, there must be at least one warning explaining why."""
        result = score_recipe("Test Recipe", [], ingredients, profiles)
        if result["blocked"]:
            assert len(result["warnings"]) > 0

    @given(ingredients=st.lists(SAFE_NAMES, max_size=10))
    @settings(max_examples=200)
    def test_no_profiles_no_block(self, ingredients):
        """With no profiles and no overrides, a recipe is never blocked."""
        result = score_recipe("Test Recipe", [], ingredients, diner_profiles=[])
        assert result["blocked"] is False
        assert result["score"] == 100

    @given(rating=st.floats(min_value=1.0, max_value=5.0))
    @settings(max_examples=100)
    def test_rating_adjusts_from_base(self, rating):
        """Rating factor adjusts score predictably from the base of 100."""
        result = score_recipe("Test", [], ["chicken"], [], average_rating=rating)
        expected = 100 + int((rating - 3) * 10)
        assert result["score"] == expected

    @given(
        rating_a=st.floats(min_value=1.0, max_value=5.0),
        rating_b=st.floats(min_value=1.0, max_value=5.0),
    )
    @settings(max_examples=100)
    def test_higher_rating_means_higher_score(self, rating_a, rating_b):
        """A higher average rating always produces a higher or equal score."""
        assume(rating_b > rating_a)
        result_a = score_recipe("Test", [], ["chicken"], [], average_rating=rating_a)
        result_b = score_recipe("Test", [], ["chicken"], [], average_rating=rating_b)
        assert result_b["score"] >= result_a["score"]


# ---------------------------------------------------------------------------
# CANNOT severity: safety-critical properties
# ---------------------------------------------------------------------------


class TestCannotSafetyProperties:
    """CANNOT is life-or-death — these properties must NEVER fail."""

    @given(
        member=st.sampled_from(["Dave", "Lisa", "David", "Hannah"]),
        group_and_ingredient=st.sampled_from(
            [(group, member) for group, members in INGREDIENT_GROUPS.items() for member in members]
        ),
    )
    @settings(max_examples=300)
    def test_cannot_group_blocks_matching_ingredient(self, member, group_and_ingredient):
        """If a diner CANNOT eat a group, any ingredient in that group blocks the recipe."""
        group, ingredient = group_and_ingredient
        profiles = [
            {
                "member_name": member,
                "item": group,
                "item_type": "ingredient",
                "severity": "cannot",
                "reason": "allergy",
            }
        ]
        result = score_recipe("Test", [], [ingredient], profiles)
        assert result["blocked"] is True, (
            f"CANNOT {group} did not block recipe containing {ingredient}"
        )

    @given(
        member=st.sampled_from(["Dave", "Lisa", "David"]),
        ingredient=st.sampled_from(ALL_GROUP_MEMBERS),
    )
    @settings(max_examples=200)
    def test_cannot_member_blocks_sibling(self, member, ingredient):
        """If diner CANNOT eat a specific group member, sibling items also block."""
        # Find a sibling in the same group
        from cook.scoring import _SIBLING_ITEMS

        siblings = _SIBLING_ITEMS.get(ingredient, set())
        assume(len(siblings) > 1)  # needs at least one other sibling
        other = next(s for s in siblings if s != ingredient)

        profiles = [
            {
                "member_name": member,
                "item": ingredient,
                "item_type": "ingredient",
                "severity": "cannot",
                "reason": "allergy",
            }
        ]
        result = score_recipe("Test", [], [other], profiles)
        assert result["blocked"] is True, f"CANNOT {ingredient} did not block sibling {other}"

    @given(
        member=st.sampled_from(["Dave", "Lisa"]),
        group=st.sampled_from(GROUP_KEYS),
    )
    @settings(max_examples=100)
    def test_cannot_with_no_matching_ingredient_does_not_block(self, member, group):
        """CANNOT only blocks if the recipe actually contains a matching ingredient."""
        profiles = [
            {
                "member_name": member,
                "item": group,
                "item_type": "ingredient",
                "severity": "cannot",
                "reason": "allergy",
            }
        ]
        # Use ingredients guaranteed not to match any group
        result = score_recipe("Test", [], ["chicken", "rice", "tomato"], profiles)
        assert result["blocked"] is False


# ---------------------------------------------------------------------------
# Override dominance
# ---------------------------------------------------------------------------


class TestOverrideProperties:
    """Overrides must always take effect regardless of profiles."""

    @given(
        member=st.sampled_from(["Dave", "Lisa", "David"]),
        profiles=st.lists(st_profile(), max_size=5),
    )
    @settings(max_examples=100)
    def test_cannot_override_always_blocks(self, member, profiles):
        """A CANNOT override blocks the recipe no matter what profiles say."""
        overrides = [
            {
                "member_name": member,
                "suitability": "cannot",
                "reason": "manual",
            }
        ]
        result = score_recipe("Test", [], ["chicken"], profiles, overrides=overrides)
        assert result["blocked"] is True

    @given(
        suitability=st.sampled_from(["likes", "loves"]),
        member=st.sampled_from(["Dave", "Lisa"]),
    )
    @settings(max_examples=50)
    def test_positive_override_adds_bonus(self, suitability, member):
        """likes/loves overrides produce a bonus message."""
        overrides = [{"member_name": member, "suitability": suitability}]
        result = score_recipe("Test", [], ["chicken"], [], overrides=overrides)
        assert any(member in b for b in result["bonuses"])


# ---------------------------------------------------------------------------
# Unresolved ingredients
# ---------------------------------------------------------------------------


class TestUnresolvedProperties:
    """Property tests for the unresolved ingredient detection."""

    @given(
        real_names=st.lists(
            st.sampled_from(["chicken", "onion", "garlic", "pepper", "tomato"]),
            min_size=3,
            max_size=10,
        ),
    )
    @settings(max_examples=100)
    def test_all_real_names_never_unresolved(self, real_names):
        """Lists of real ingredient names are never flagged as unresolved."""
        assert not _has_unresolved_ingredients(real_names)

    @given(
        ids=st.lists(
            st.from_regex(r"^[0-9]{6,12}$", fullmatch=True),
            min_size=3,
            max_size=10,
        ),
    )
    @settings(max_examples=100)
    def test_all_numeric_ids_always_unresolved(self, ids):
        """Lists of pure numeric IDs are always flagged as unresolved."""
        assert _has_unresolved_ingredients(ids)

    @given(st.lists(st.text(), max_size=0))
    def test_empty_list_never_unresolved(self, empty):
        """Empty ingredient lists are never unresolved."""
        assert not _has_unresolved_ingredients(empty)


# ---------------------------------------------------------------------------
# Ingredient matching: symmetry and consistency
# ---------------------------------------------------------------------------


class TestIngredientMatchingProperties:
    """Properties for the ingredient matching logic."""

    @given(ingredient=st.sampled_from(ALL_GROUP_MEMBERS))
    @settings(max_examples=100)
    def test_group_member_matches_own_group(self, ingredient):
        """Every group member must match at least one group key."""
        from cook.scoring import _INGREDIENT_TO_GROUPS

        groups = _INGREDIENT_TO_GROUPS[ingredient]
        for group in groups:
            assert _ingredient_matches_profile(ingredient, group, "ingredient"), (
                f"{ingredient} should match group {group}"
            )

    @given(
        group_and_member=st.sampled_from(
            [(group, member) for group, members in INGREDIENT_GROUPS.items() for member in members]
        ),
    )
    @settings(max_examples=200)
    def test_group_expansion_is_consistent(self, group_and_member):
        """If member is in INGREDIENT_GROUPS[group], then matching must succeed."""
        group, member = group_and_member
        assert _ingredient_matches_profile(member, group, "ingredient")

    @given(
        ingredient=st.text(min_size=1, max_size=30),
        profile_item=st.text(min_size=1, max_size=30),
    )
    @settings(max_examples=200)
    def test_case_insensitive(self, ingredient, profile_item):
        """Matching must be case-insensitive."""
        result_lower = _ingredient_matches_profile(
            ingredient.lower(), profile_item.lower(), "ingredient"
        )
        result_mixed = _ingredient_matches_profile(ingredient, profile_item, "ingredient")
        assert result_lower == result_mixed

    @given(
        ingredient=st.text(min_size=1, max_size=20),
        profile_item=st.text(min_size=1, max_size=20),
        item_type=st.sampled_from(["cuisine", "dish"]),
    )
    @settings(max_examples=100)
    def test_ignores_non_ingredient_types(self, ingredient, profile_item, item_type):
        """_ingredient_matches_profile only works for ingredient/category types."""
        assert not _ingredient_matches_profile(ingredient, profile_item, item_type)


# ---------------------------------------------------------------------------
# Cuisine and dish matching
# ---------------------------------------------------------------------------


class TestCuisineMatchingProperties:
    @given(
        tags=st.lists(st.text(min_size=1, max_size=20), max_size=5),
        item=st.text(min_size=1, max_size=20),
    )
    @settings(max_examples=100)
    def test_ignores_ingredient_type(self, tags, item):
        """Cuisine matching never fires for item_type='ingredient'."""
        assert not _cuisine_matches_profile(tags, item, "ingredient")

    def test_empty_tags_never_match(self):
        assert not _cuisine_matches_profile([], "anything", "cuisine")


class TestDishMatchingProperties:
    @given(
        name=st.text(min_size=1, max_size=50),
        item=st.text(min_size=1, max_size=50),
    )
    @settings(max_examples=100)
    def test_ignores_non_dish_types(self, name, item):
        """Dish matching only works for item_type='dish'."""
        assert not _dish_matches_profile(name, item, "ingredient")
        assert not _dish_matches_profile(name, item, "cuisine")
        assert not _dish_matches_profile(name, item, "category")
