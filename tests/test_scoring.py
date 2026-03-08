"""Tests for the recipe suitability scorer.

Covers:
- Severity scoring (blocked, penalties, bonuses)
- Ingredient group expansion (dairy, wheat, fish, etc.)
- Cuisine/tag matching
- Dish name matching
- Rating factor
- Edge cases (empty profiles, empty ingredients)
"""

from cook.scoring import (
    INGREDIENT_GROUPS,
    _cuisine_matches_profile,
    _dish_matches_profile,
    _has_unresolved_ingredients,
    _ingredient_matches_profile,
    score_recipe,
)


# ---------------------------------------------------------------------------
# Ingredient matching
# ---------------------------------------------------------------------------


class TestIngredientMatching:
    """Test _ingredient_matches_profile with direct and group matches."""

    def test_direct_substring_match(self):
        assert _ingredient_matches_profile("butter", "butter", "ingredient")

    def test_ingredient_contains_profile_item(self):
        assert _ingredient_matches_profile("salted butter", "butter", "ingredient")

    def test_profile_item_contains_ingredient(self):
        assert _ingredient_matches_profile("milk", "whole milk", "ingredient")

    def test_no_match(self):
        assert not _ingredient_matches_profile("chicken", "beef", "ingredient")

    def test_group_expansion_dairy(self):
        assert _ingredient_matches_profile("cream", "dairy", "ingredient")
        assert _ingredient_matches_profile("butter", "dairy", "ingredient")
        assert _ingredient_matches_profile("cheese", "dairy", "ingredient")
        assert not _ingredient_matches_profile("chicken", "dairy", "ingredient")

    def test_group_expansion_wheat(self):
        assert _ingredient_matches_profile("flour", "wheat", "ingredient")
        assert _ingredient_matches_profile("pasta", "wheat", "ingredient")
        assert _ingredient_matches_profile("breadcrumbs", "wheat", "ingredient")
        assert not _ingredient_matches_profile("rice", "wheat", "ingredient")

    def test_group_expansion_fish(self):
        assert _ingredient_matches_profile("salmon", "fish", "category")
        assert _ingredient_matches_profile("cod fillet", "fish", "category")
        assert not _ingredient_matches_profile("chicken", "fish", "category")

    def test_group_expansion_nuts(self):
        assert _ingredient_matches_profile("almond", "nuts", "ingredient")
        assert _ingredient_matches_profile("cashew nuts", "nuts", "ingredient")

    def test_ignores_cuisine_type(self):
        assert not _ingredient_matches_profile("butter", "butter", "cuisine")

    def test_ignores_dish_type(self):
        assert not _ingredient_matches_profile("pasta", "pasta", "dish")

    def test_sibling_expansion_milk_matches_yoghurt(self):
        """Profile says 'milk' — should match 'yoghurt' (both dairy siblings)."""
        assert _ingredient_matches_profile("greek yoghurt", "milk", "ingredient")

    def test_sibling_expansion_milk_matches_cream(self):
        assert _ingredient_matches_profile("double cream", "milk", "ingredient")

    def test_sibling_expansion_milk_matches_butter(self):
        assert _ingredient_matches_profile("butter", "milk", "ingredient")

    def test_sibling_expansion_milk_matches_cheese(self):
        assert _ingredient_matches_profile("cheddar cheese", "milk", "ingredient")

    def test_sibling_expansion_flour_matches_pasta(self):
        """Profile says 'flour' — should match 'pasta' (both wheat siblings)."""
        assert _ingredient_matches_profile("pasta", "flour", "ingredient")

    def test_sibling_no_cross_group(self):
        """Milk and flour are in different groups — no sibling match."""
        assert not _ingredient_matches_profile("flour", "milk", "ingredient")

    def test_case_insensitive(self):
        assert _ingredient_matches_profile("Butter", "butter", "ingredient")
        assert _ingredient_matches_profile("butter", "Dairy", "ingredient")


# ---------------------------------------------------------------------------
# Cuisine/tag matching
# ---------------------------------------------------------------------------


class TestCuisineMatching:
    """Test _cuisine_matches_profile with recipe tags."""

    def test_direct_tag_match(self):
        assert _cuisine_matches_profile(["Thai", "quick"], "thai", "cuisine")

    def test_partial_tag_match(self):
        assert _cuisine_matches_profile(["Thai food"], "thai", "cuisine")

    def test_no_match(self):
        assert not _cuisine_matches_profile(["Italian", "pasta"], "thai", "cuisine")

    def test_ignores_ingredient_type(self):
        assert not _cuisine_matches_profile(["Thai"], "thai", "ingredient")

    def test_category_type_also_matches(self):
        assert _cuisine_matches_profile(["Thai"], "thai", "category")

    def test_empty_tags(self):
        assert not _cuisine_matches_profile([], "thai", "cuisine")


# ---------------------------------------------------------------------------
# Dish name matching
# ---------------------------------------------------------------------------


class TestDishMatching:
    """Test _dish_matches_profile with recipe names."""

    def test_direct_match(self):
        assert _dish_matches_profile("Fish Pie", "fish pie", "dish")

    def test_partial_match(self):
        assert _dish_matches_profile("Pepperoni Pizza with Olives", "pepperoni pizza", "dish")

    def test_no_match(self):
        assert not _dish_matches_profile("Chicken Tikka", "fish pie", "dish")

    def test_ignores_ingredient_type(self):
        assert not _dish_matches_profile("Fish Pie", "fish pie", "ingredient")


# ---------------------------------------------------------------------------
# Full recipe scoring
# ---------------------------------------------------------------------------


class TestScoreRecipe:
    """Test the complete score_recipe function."""

    def test_no_profiles_returns_base_score(self):
        result = score_recipe(
            recipe_name="Chicken Tikka",
            recipe_tags=["Indian"],
            ingredient_names=["chicken", "yoghurt", "spices"],
            diner_profiles=[],
        )
        assert result["score"] == 100
        assert result["blocked"] is False
        assert result["warnings"] == []
        assert result["bonuses"] == []

    def test_cannot_blocks_recipe(self):
        result = score_recipe(
            recipe_name="Pasta Bake",
            recipe_tags=["Italian"],
            ingredient_names=["pasta", "cheese", "tomato"],
            diner_profiles=[
                {
                    "member_name": "David",
                    "item": "wheat",
                    "item_type": "ingredient",
                    "severity": "cannot",
                    "reason": "intolerance",
                },
            ],
        )
        assert result["blocked"] is True
        assert result["score"] < 0
        assert any("David" in w and "wheat" in w for w in result["warnings"])

    def test_dislikes_adds_penalty(self):
        result = score_recipe(
            recipe_name="Salmon Fillet",
            recipe_tags=["healthy"],
            ingredient_names=["salmon", "lemon", "dill"],
            diner_profiles=[
                {
                    "member_name": "Dave",
                    "item": "fish",
                    "item_type": "category",
                    "severity": "dislikes",
                    "reason": "preference",
                },
            ],
        )
        assert result["blocked"] is False
        assert result["score"] == 80  # 100 - 20
        assert any("Dave" in w and "dislikes" in w for w in result["warnings"])

    def test_likes_adds_bonus(self):
        result = score_recipe(
            recipe_name="Thai Green Curry",
            recipe_tags=["Thai", "curry"],
            ingredient_names=["chicken", "coconut milk", "thai basil"],
            diner_profiles=[
                {
                    "member_name": "Lisa",
                    "item": "thai",
                    "item_type": "cuisine",
                    "severity": "likes",
                    "reason": None,
                },
            ],
        )
        assert result["blocked"] is False
        assert result["score"] == 115  # 100 + 15
        assert any("Lisa" in b and "likes" in b for b in result["bonuses"])

    def test_loves_adds_larger_bonus(self):
        result = score_recipe(
            recipe_name="Thai Green Curry",
            recipe_tags=["Thai"],
            ingredient_names=["chicken"],
            diner_profiles=[
                {
                    "member_name": "Lisa",
                    "item": "thai",
                    "item_type": "cuisine",
                    "severity": "loves",
                    "reason": None,
                },
            ],
        )
        assert result["score"] == 130  # 100 + 30

    def test_multiple_diners_combined(self):
        result = score_recipe(
            recipe_name="Thai Chicken Noodles",
            recipe_tags=["Thai"],
            ingredient_names=["chicken", "noodles", "soy sauce"],
            diner_profiles=[
                {
                    "member_name": "David",
                    "item": "wheat",
                    "item_type": "ingredient",
                    "severity": "cannot",
                    "reason": "intolerance",
                },
                {
                    "member_name": "Lisa",
                    "item": "thai",
                    "item_type": "cuisine",
                    "severity": "likes",
                    "reason": None,
                },
            ],
        )
        # David can't eat wheat (noodles match wheat group) → blocked
        assert result["blocked"] is True
        assert any("David" in w for w in result["warnings"])
        # Lisa still gets her bonus
        assert any("Lisa" in b for b in result["bonuses"])

    def test_rating_factor_positive(self):
        result = score_recipe(
            recipe_name="Something",
            recipe_tags=[],
            ingredient_names=["chicken"],
            diner_profiles=[],
            average_rating=5.0,
        )
        assert result["score"] == 120  # 100 + (5-3)*10

    def test_rating_factor_negative(self):
        result = score_recipe(
            recipe_name="Something",
            recipe_tags=[],
            ingredient_names=["chicken"],
            diner_profiles=[],
            average_rating=1.0,
        )
        assert result["score"] == 80  # 100 + (1-3)*10

    def test_empty_ingredients_no_matches(self):
        result = score_recipe(
            recipe_name="Mystery Dish",
            recipe_tags=[],
            ingredient_names=[],
            diner_profiles=[
                {
                    "member_name": "David",
                    "item": "wheat",
                    "item_type": "ingredient",
                    "severity": "cannot",
                    "reason": "intolerance",
                },
            ],
        )
        assert result["blocked"] is False
        assert result["score"] == 100

    def test_sibling_blocks_milk_on_yoghurt(self):
        """CANNOT milk should block a recipe containing yoghurt."""
        result = score_recipe(
            recipe_name="Yoghurt Parfait",
            recipe_tags=[],
            ingredient_names=["greek yoghurt", "strawberries", "granola"],
            diner_profiles=[
                {
                    "member_name": "David",
                    "item": "milk",
                    "item_type": "ingredient",
                    "severity": "cannot",
                    "reason": "intolerance",
                },
            ],
        )
        assert result["blocked"] is True
        assert any("David" in w and "milk" in w for w in result["warnings"])

    def test_unresolved_ingredients_penalised_with_cannot(self):
        """Numeric product IDs + CANNOT profiles = penalty + warning."""
        result = score_recipe(
            recipe_name="Yorkshire Puddings",
            recipe_tags=["beef"],
            ingredient_names=["562544011", "509771011", "518717011"],
            diner_profiles=[
                {
                    "member_name": "David",
                    "item": "wheat",
                    "item_type": "ingredient",
                    "severity": "cannot",
                    "reason": "intolerance",
                },
            ],
        )
        assert result["score"] == 50  # 100 - 50 penalty
        assert any("not verified" in w for w in result["warnings"])
        assert any("David" in w for w in result["warnings"])

    def test_unresolved_ingredients_no_penalty_without_cannot(self):
        """Numeric product IDs but no CANNOT profiles = no penalty."""
        result = score_recipe(
            recipe_name="Something",
            recipe_tags=[],
            ingredient_names=["562544011", "509771011"],
            diner_profiles=[
                {
                    "member_name": "Lisa",
                    "item": "thai",
                    "item_type": "cuisine",
                    "severity": "likes",
                    "reason": None,
                },
            ],
        )
        assert result["score"] == 100  # no penalty
        assert not any("not verified" in w for w in result["warnings"])

    def test_mixed_resolved_unresolved_under_threshold(self):
        """Mostly real ingredient names with a few IDs = no penalty."""
        result = score_recipe(
            recipe_name="Chicken Dish",
            recipe_tags=[],
            ingredient_names=["chicken", "onion", "garlic", "562544011"],
            diner_profiles=[
                {
                    "member_name": "David",
                    "item": "wheat",
                    "item_type": "ingredient",
                    "severity": "cannot",
                    "reason": "intolerance",
                },
            ],
        )
        assert result["score"] == 100
        assert not any("not verified" in w for w in result["warnings"])


class TestUnresolvedIngredients:
    """Test _has_unresolved_ingredients helper."""

    def test_all_numeric(self):
        assert _has_unresolved_ingredients(["123456", "789012", "345678"])

    def test_all_real(self):
        assert not _has_unresolved_ingredients(["chicken", "onion", "garlic"])

    def test_mostly_numeric(self):
        assert _has_unresolved_ingredients(["123456", "789012", "chicken"])

    def test_mostly_real(self):
        assert not _has_unresolved_ingredients(["chicken", "onion", "123456", "garlic"])

    def test_empty(self):
        assert not _has_unresolved_ingredients([])


class TestRecipeOverrides:
    """Test manual per-member per-recipe overrides."""

    def test_cannot_override_blocks_recipe(self):
        result = score_recipe(
            recipe_name="Beef Koftas",
            recipe_tags=[],
            ingredient_names=["beef mince", "flame-baked rotis"],
            diner_profiles=[],
            overrides=[
                {
                    "member_name": "David",
                    "suitability": "cannot",
                    "reason": "contains wheat via roti",
                },
            ],
        )
        assert result["blocked"] is True
        assert result["score"] < 0
        assert any("David" in w and "manual override" in w for w in result["warnings"])

    def test_dislikes_override_penalises(self):
        result = score_recipe(
            recipe_name="Something",
            recipe_tags=[],
            ingredient_names=["chicken"],
            diner_profiles=[],
            overrides=[
                {"member_name": "Dave", "suitability": "dislikes", "reason": "too bland"},
            ],
        )
        assert result["blocked"] is False
        assert result["score"] == 80  # 100 - 20

    def test_loves_override_boosts(self):
        result = score_recipe(
            recipe_name="Thai Curry",
            recipe_tags=[],
            ingredient_names=["chicken"],
            diner_profiles=[],
            overrides=[
                {"member_name": "Lisa", "suitability": "loves"},
            ],
        )
        assert result["score"] == 130  # 100 + 30
        assert any("Lisa" in b and "loves" in b for b in result["bonuses"])

    def test_override_stacks_with_profiles(self):
        """Override and profile scoring combine."""
        result = score_recipe(
            recipe_name="Beef Koftas",
            recipe_tags=[],
            ingredient_names=["beef mince", "flame-baked rotis"],
            diner_profiles=[
                {
                    "member_name": "Lisa",
                    "item": "thai",
                    "item_type": "cuisine",
                    "severity": "likes",
                    "reason": None,
                },
            ],
            overrides=[
                {"member_name": "David", "suitability": "cannot", "reason": "wheat in roti"},
            ],
        )
        assert result["blocked"] is True

    def test_no_overrides_is_fine(self):
        result = score_recipe(
            recipe_name="Plain Chicken",
            recipe_tags=[],
            ingredient_names=["chicken"],
            diner_profiles=[],
            overrides=None,
        )
        assert result["score"] == 100
        assert result["blocked"] is False

    def test_override_reason_in_warning(self):
        result = score_recipe(
            recipe_name="Beef Koftas",
            recipe_tags=[],
            ingredient_names=["beef mince"],
            diner_profiles=[],
            overrides=[
                {
                    "member_name": "David",
                    "suitability": "cannot",
                    "reason": "contains wheat via roti",
                },
            ],
        )
        assert any("contains wheat via roti" in w for w in result["warnings"])

    def test_override_substitution_field_ignored_by_scorer(self):
        """Substitution is stored in DB but doesn't affect scoring — just informational."""
        result = score_recipe(
            recipe_name="Wraps",
            recipe_tags=[],
            ingredient_names=["flour tortilla"],
            diner_profiles=[],
            overrides=[
                {
                    "member_name": "David",
                    "suitability": "cannot",
                    "reason": "wheat in tortilla",
                    "substitution": "use corn tortillas",
                },
            ],
        )
        assert result["blocked"] is True


class TestExpandedWheatGroup:
    """Verify the expanded wheat/gluten group catches common bread products."""

    def test_roti_matches_wheat(self):
        assert _ingredient_matches_profile("flame-baked rotis", "wheat", "ingredient")

    def test_naan_matches_wheat(self):
        assert _ingredient_matches_profile("garlic naan", "wheat", "ingredient")

    def test_tortilla_matches_wheat(self):
        assert _ingredient_matches_profile("flour tortilla", "wheat", "ingredient")

    def test_toast_matches_wheat(self):
        assert _ingredient_matches_profile("toast", "wheat", "ingredient")

    def test_pitta_matches_wheat(self):
        assert _ingredient_matches_profile("pitta bread", "wheat", "ingredient")

    def test_ciabatta_matches_wheat(self):
        assert _ingredient_matches_profile("ciabatta", "wheat", "ingredient")

    def test_focaccia_matches_gluten(self):
        assert _ingredient_matches_profile("focaccia", "gluten", "ingredient")

    def test_flatbread_matches_wheat(self):
        assert _ingredient_matches_profile("flatbread", "wheat", "ingredient")

    def test_corn_tortilla_does_not_match_wheat(self):
        """'corn tortilla' DOES match wheat because 'tortilla' is in the name.
        This is a known trade-off — corn tortillas get caught by the group match.
        The override system handles this: mark the recipe as suitable with a substitution note."""
        # This is intentional — false positives are safer than false negatives for CANNOT
        assert _ingredient_matches_profile("corn tortilla", "wheat", "ingredient")


class TestExpandedDairyGroup:
    """Verify the expanded dairy group catches prepared dairy products."""

    def test_tzatziki_matches_dairy(self):
        assert _ingredient_matches_profile("tzatziki", "dairy", "ingredient")

    def test_mozzarella_matches_dairy(self):
        assert _ingredient_matches_profile("mozzarella", "dairy", "ingredient")

    def test_parmesan_matches_dairy(self):
        assert _ingredient_matches_profile("parmesan", "dairy", "ingredient")

    def test_paneer_matches_dairy(self):
        assert _ingredient_matches_profile("paneer tikka", "dairy", "ingredient")


class TestIngredientGroups:
    """Verify ingredient group integrity."""

    def test_all_groups_have_members(self):
        for group, members in INGREDIENT_GROUPS.items():
            assert len(members) > 0, f"Group '{group}' has no members"

    def test_members_are_lowercase(self):
        for group, members in INGREDIENT_GROUPS.items():
            for member in members:
                assert member == member.lower(), f"'{member}' in group '{group}' is not lowercase"

    def test_wheat_and_gluten_are_identical(self):
        assert INGREDIENT_GROUPS["wheat"] == INGREDIENT_GROUPS["gluten"]
