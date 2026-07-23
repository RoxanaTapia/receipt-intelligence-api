"""Budget and diet insight heuristics (#10).

Pure functions over ``SummaryResponse`` — transparent thresholds, no Claude.
Lifestyle spending signals only; not medical or nutritional advice.
"""

from __future__ import annotations

from app.analytics_models import CategoryShare, SummaryResponse
from app.insight_models import Insight, InsightSeverity
from app.models import Category

# Documented thresholds — keep in sync with docs/question-answering.md (#10).
# snacks / (food + snacks): flag when snacks take a large slice of grocery spend.
SNACKS_SHARE_OF_GROCERY_WARN_PCT: float = 20.0
# (snacks + drinks) / total: flag when discretionary categories dominate.
HIGH_DISCRETIONARY_WARN_PCT: float = 40.0


def generate_insights(
    summary: SummaryResponse,
    *,
    snacks_share_warn_pct: float = SNACKS_SHARE_OF_GROCERY_WARN_PCT,
    discretionary_warn_pct: float = HIGH_DISCRETIONARY_WARN_PCT,
) -> list[Insight]:
    """Build the three insight types from a structured summary."""
    spend = _spend_by_category(summary.by_category)
    period = summary.period_label
    total = summary.total_spend

    return [
        _snacks_share_of_grocery(spend, period, snacks_share_warn_pct),
        _top_spend_category(summary, period, total),
        _high_discretionary_share(spend, period, total, discretionary_warn_pct),
    ]


def _spend_by_category(rows: list[CategoryShare]) -> dict[Category, float]:
    return {row.category: row.total_spend for row in rows}


def _category_spend(spend: dict[Category, float], category: Category) -> float:
    return spend.get(category, 0.0)


def _share_pct(part: float, whole: float) -> float:
    if whole == 0:
        return 0.0
    return round((part / whole) * 100, 1)


def _snacks_share_of_grocery(
    spend: dict[Category, float],
    period_label: str,
    warn_pct: float,
) -> Insight:
    food = _category_spend(spend, Category.FOOD)
    snacks = _category_spend(spend, Category.SNACKS)
    grocery = food + snacks
    value = _share_pct(snacks, grocery)
    triggered = grocery > 0 and value > warn_pct
    text = (
        f"Snacks were {value:.1f}% of your grocery spend (food + snacks) "
        f"{period_label}."
    )
    if triggered:
        text += f" That's above the {warn_pct:g}% guideline."
    return Insight(
        insight_type="snacks_share_of_grocery",
        severity=InsightSeverity.WARNING if triggered else InsightSeverity.OK,
        triggered=triggered,
        value=value,
        threshold=warn_pct,
        unit="%",
        text=text,
    )


def _top_spend_category(
    summary: SummaryResponse,
    period_label: str,
    total: float,
) -> Insight:
    if total == 0 or not summary.top_categories:
        return Insight(
            insight_type="top_spend_category",
            severity=InsightSeverity.INFO,
            triggered=False,
            value=0.0,
            threshold=None,
            unit="%",
            text=f"No spending recorded {period_label}.",
        )

    top = summary.top_categories[0]
    text = (
        f"Your top category {period_label} was {top.category.value} "
        f"at {top.percentage:.1f}% of total spend "
        f"({top.total_spend:.2f} EUR)."
    )
    return Insight(
        insight_type="top_spend_category",
        severity=InsightSeverity.INFO,
        triggered=True,
        value=top.percentage,
        threshold=None,
        unit="%",
        text=text,
    )


def _high_discretionary_share(
    spend: dict[Category, float],
    period_label: str,
    total: float,
    warn_pct: float,
) -> Insight:
    discretionary = (
        _category_spend(spend, Category.SNACKS)
        + _category_spend(spend, Category.DRINKS)
    )
    value = _share_pct(discretionary, total)
    triggered = total > 0 and value > warn_pct
    text = (
        f"Snacks and drinks together were {value:.1f}% of your total spend "
        f"{period_label}."
    )
    if triggered:
        text += f" That's above the {warn_pct:g}% guideline."
    return Insight(
        insight_type="high_discretionary_share",
        severity=InsightSeverity.WARNING if triggered else InsightSeverity.OK,
        triggered=triggered,
        value=value,
        threshold=warn_pct,
        unit="%",
        text=text,
    )
