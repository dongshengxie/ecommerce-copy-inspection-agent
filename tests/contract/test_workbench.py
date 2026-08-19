from __future__ import annotations

import pytest
from pydantic import ValidationError

from contracts.workbench import WorkbenchInspectionSubmission, to_product_input


def _valid_submission() -> dict[str, object]:
    return {
        "category": "食品",
        "title": "茉莉花茶袋泡茶 30g",
        "selling_points": ["独立袋泡", "花香清雅"],
        "description": "茉莉花茶，适合日常冲泡。",
        "attributes": {
            "ingredients": "绿茶、茉莉花",
            "shelf_life": "18个月",
            "storage_method": "密封、避光保存",
            "origin": "浙江杭州",
        },
        "marketing_description": "30g 盒装。",
    }


def test_workbench_submission_excludes_client_supplied_internal_identity_fields() -> None:
    payload = _valid_submission()
    payload["product_id"] = "client-controlled"

    with pytest.raises(ValidationError):
        WorkbenchInspectionSubmission.model_validate(payload)


def test_workbench_submission_maps_to_server_generated_product_identity() -> None:
    submission = WorkbenchInspectionSubmission.model_validate(_valid_submission())

    product = to_product_input(submission)

    assert product.product_id.startswith("workbench-")
    assert product.product_revision == 1
    assert product.trigger_source == "vue_workbench"
    assert product.title == submission.title
    assert product.attributes.ingredients == submission.attributes.ingredients
