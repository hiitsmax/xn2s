from __future__ import annotations

from ..backend import DigestBackend
from ..config import DEFAULT_DROP_CATEGORIES
from ..models import AssembledUnit, CategorizedUnit, FilteredUnit, TaxonomyConfig


def categorize_units(
    *,
    backend: DigestBackend,
    taxonomy: TaxonomyConfig,
    units: list[AssembledUnit],
) -> list[CategorizedUnit]:
    allowed_categories = {category.slug for category in taxonomy.categories}
    categorized: list[CategorizedUnit] = []
    for unit in units:
        result = backend.categorize_conversation(taxonomy=taxonomy, unit=unit)
        category = result.category if result.category in allowed_categories else "analysis"
        categorized.append(
            CategorizedUnit(
                **unit.model_dump(),
                category=category,
                subcategory=result.subcategory,
                editorial_angle=result.editorial_angle,
                reasoning=result.reasoning,
            )
        )
    return categorized


def filter_units(
    *,
    categorized_units: list[CategorizedUnit],
    taxonomy: TaxonomyConfig,
) -> list[FilteredUnit]:
    drop_categories = set(taxonomy.drop_categories or DEFAULT_DROP_CATEGORIES)
    filtered: list[FilteredUnit] = []
    for unit in categorized_units:
        keep = unit.category not in drop_categories
        filter_reason = (
            "kept_for_signal" if keep else f"dropped_due_to_category:{unit.category}"
        )
        filtered.append(
            FilteredUnit(
                **unit.model_dump(),
                keep=keep,
                filter_reason=filter_reason,
            )
        )
    return filtered
