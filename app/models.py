"""Pydantic models for categorized receipt JSON and flattened line items."""

from enum import Enum

from pydantic import BaseModel, Field


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
    merchant: str
    date: str
    total: float
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
