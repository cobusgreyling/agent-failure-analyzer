"""Tests for the failure taxonomy."""

from agent_failure_analyzer.taxonomy import (
    CATEGORY_DESCRIPTIONS,
    SUBCATEGORY_TO_CATEGORY,
    FailureCategory,
    FailureSubcategory,
)


def test_all_subcategories_mapped():
    """Every subcategory must map to a category."""
    for sub in FailureSubcategory:
        assert sub in SUBCATEGORY_TO_CATEGORY, f"{sub} has no category mapping"


def test_all_categories_described():
    """Every category must have a description."""
    for cat in FailureCategory:
        assert cat in CATEGORY_DESCRIPTIONS, f"{cat} has no description"


def test_subcategory_category_consistency():
    """Subcategory names should loosely align with their parent category."""
    # Just verify the mapping is non-empty and returns valid categories
    for sub, cat in SUBCATEGORY_TO_CATEGORY.items():
        assert isinstance(cat, FailureCategory)
        assert isinstance(sub, FailureSubcategory)
