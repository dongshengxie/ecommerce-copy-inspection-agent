from __future__ import annotations

from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict

from contracts.models import FoodAttributes, ProductInput


class WorkbenchInspectionSubmission(BaseModel):
    """Food copy submitted from the standalone workbench without internal identity fields."""

    model_config = ConfigDict(extra="forbid")

    category: Literal["食品"]
    title: str
    selling_points: list[str]
    description: str
    attributes: FoodAttributes
    marketing_description: str


def to_product_input(submission: WorkbenchInspectionSubmission) -> ProductInput:
    """Assign server-controlled task identity before invoking the frozen inspection Contract."""

    return ProductInput(
        product_id=f"workbench-{uuid4()}",
        product_revision=1,
        trigger_source="vue_workbench",
        **submission.model_dump(),
    )
