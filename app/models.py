"""Pydantic models for categorized receipt JSON and flattened line items."""

from enum import Enum

from pydantic import AliasChoices, BaseModel, ConfigDict, Field


class Category(str, Enum):
    """Spending categories from the upstream categorization schema."""

    FOOD = "food"
    SNACKS = "snacks"
    DRINKS = "drinks"
    HOUSEHOLD = "household"
    OTHER = "other"


class LineItem(BaseModel):
    description: str
    quantity: float
    price: float
    category: Category


class CategorizedReceipt(BaseModel):
    """One categorized receipt file written by n8n.

    ``total`` is the amount printed on the receipt (extracted), not a
    recomputed sum of line items. Tax and fees are included in the printed
    total check only when they are *not* already line items.
    """

    model_config = ConfigDict(populate_by_name=True)

    merchant: str
    date: str
    total: float | None = Field(
        default=None,
        validation_alias=AliasChoices("total", "printed_total"),
        description=(
            "Amount printed on the receipt (Summe/Total). Optional so a missing "
            "printed total can be reported instead of skipping the file."
        ),
    )
    tax: float | None = Field(
        default=None,
        description="Printed tax when it is not already included as a line item.",
    )
    fees: float | None = Field(
        default=None,
        description="Printed fees when they are not already included as line items.",
    )
    line_items: list[LineItem] = Field(min_length=1)
    extracted_at: str | None = None
    categorized_at: str | None = None


class LineItemRecord(BaseModel):
    """One queryable row: receipt context plus a single line item."""

    date: str
    merchant: str
    category: Category
    price: float
    quantity: float
    description: str
