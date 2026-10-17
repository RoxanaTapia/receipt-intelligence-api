"""HTTP tests for analytics REST endpoints (#6)."""

from datetime import date
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app
from app.models import Category
from app.routers.analytics import get_data_path

AGG_FIXTURES = Path(__file__).parent / "fixtures" / "aggregation"


def _client(data_path: Path) -> TestClient:
    app.dependency_overrides[get_data_path] = lambda: data_path
    return TestClient(app)


def teardown_function() -> None:
    app.dependency_overrides.clear()


def test_spending_explicit_range() -> None:
    client = _client(AGG_FIXTURES)
    response = client.get(
        "/analytics/spending",
        params={"start_date": "2026-05-01", "end_date": "2026-05-19"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["start_date"] == "2026-05-01"
    assert body["end_date"] == "2026-05-19"
    assert body["receipt_count"] == 3
    assert body["deduplication"]["deduplicated_count"] == 1
    assert "by_category" in body
    assert body["total_spend"] > 0


def test_spending_category_filter() -> None:
    client = _client(AGG_FIXTURES)
    response = client.get(
        "/analytics/spending",
        params={
            "start_date": "2026-05-01",
            "end_date": "2026-05-19",
            "categories": ["drinks"],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["categories"] == [Category.DRINKS.value]
    assert len(body["by_category"]) == 1
    assert body["by_category"][0]["category"] == "drinks"


def test_spending_last_n_days_preset() -> None:
    client = _client(AGG_FIXTURES)
    response = client.get(
        "/analytics/spending",
        params={"preset": "last_N_days", "n_days": 14},
    )

    assert response.status_code == 200
    body = response.json()
    assert date.fromisoformat(body["end_date"]) >= date.fromisoformat(body["start_date"])
    # Window length is inclusive: end - start + 1 == n_days
    start = date.fromisoformat(body["start_date"])
    end = date.fromisoformat(body["end_date"])
    assert (end - start).days + 1 == 14


def test_summary_explicit_range_has_facts() -> None:
    client = _client(AGG_FIXTURES)
    response = client.get(
        "/analytics/summary",
        params={"start_date": "2026-05-01", "end_date": "2026-05-19"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total_spend"] > 0
    assert body["top_categories"]
    assert any(fact["fact"] == "top_category" for fact in body["summary_facts"])


def test_insights_explicit_range() -> None:
    client = _client(AGG_FIXTURES)
    response = client.get(
        "/analytics/insights",
        params={"start_date": "2026-05-01", "end_date": "2026-05-19"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total_spend"] > 0
    assert body["period_label"]
    types = {item["insight_type"] for item in body["insights"]}
    assert types == {
        "snacks_share_of_grocery",
        "top_spend_category",
        "high_discretionary_share",
    }


def test_receipts_coverage_and_dedup() -> None:
    client = _client(AGG_FIXTURES)
    response = client.get("/analytics/receipts")

    assert response.status_code == 200
    body = response.json()
    assert body["data_path_exists"] is True
    assert body["files_loaded"] == 4
    assert body["logical_receipt_count"] == 3
    assert body["earliest_date"] == "2026-05-10"
    assert body["latest_date"] == "2026-05-19"
    assert body["deduplication"]["deduplicated_count"] == 1
    assert "2026-05-15_rewe_aaaaaaaa.json" in body["deduplication"]["superseded_files"]
    assert len(body["loaded_files"]) == 4


def test_receipts_exposes_printed_total_check() -> None:
    client = _client(AGG_FIXTURES)
    response = client.get("/analytics/receipts")

    assert response.status_code == 200
    check = response.json()["printed_total_check"]
    assert check["tolerance"] == 0.02
    assert check["match_count"] + check["mismatch_count"] + check["missing_count"] == 3
    assert check["match_count"] == 2
    assert check["mismatch_count"] == 1
    assert check["missing_count"] == 0

    by_file = {row["source_file"]: row for row in check["receipts"]}
    aldi = by_file["2026-05-10_aldi_aaaaaaaa.json"]
    assert aldi["status"] == "match"
    assert aldi["printed_total"] == 8.5
    assert aldi["computed_total"] == 8.5

    rewe = by_file["2026-05-19_rewe_cccccccc.json"]
    assert rewe["status"] == "mismatch"
    assert rewe["printed_total"] == 5.66
    assert rewe["computed_total"] == 4.07
    assert "2026-05-15_rewe_aaaaaaaa.json" not in by_file


def test_validation_rejects_unknown_category() -> None:
    client = _client(AGG_FIXTURES)
    response = client.get(
        "/analytics/spending",
        params={
            "start_date": "2026-05-01",
            "end_date": "2026-05-19",
            "categories": ["not-a-category"],
        },
    )

    assert response.status_code == 422
    assert "detail" in response.json()


def test_validation_rejects_missing_time_range() -> None:
    client = _client(AGG_FIXTURES)
    response = client.get("/analytics/spending")

    assert response.status_code == 422
    assert "detail" in response.json()


def test_validation_rejects_preset_and_explicit() -> None:
    client = _client(AGG_FIXTURES)
    response = client.get(
        "/analytics/spending",
        params={
            "preset": "last_week",
            "start_date": "2026-05-01",
            "end_date": "2026-05-07",
        },
    )

    assert response.status_code == 422


def test_empty_data_returns_clear_zero_payload(tmp_path: Path) -> None:
    client = _client(tmp_path)

    spending = client.get(
        "/analytics/spending",
        params={"start_date": "2026-01-01", "end_date": "2026-01-31"},
    )
    assert spending.status_code == 200
    body = spending.json()
    assert body["total_spend"] == 0
    assert body["receipt_count"] == 0
    assert body["by_category"] == []
    assert body["deduplication"]["deduplicated_count"] == 0

    coverage = client.get("/analytics/receipts")
    assert coverage.status_code == 200
    cov = coverage.json()
    assert cov["files_loaded"] == 0
    assert cov["logical_receipt_count"] == 0
    assert cov["earliest_date"] is None
    assert cov["latest_date"] is None
    assert cov["data_path_exists"] is True
    assert cov["printed_total_check"]["receipts"] == []
    assert cov["printed_total_check"]["match_count"] == 0


def test_openapi_includes_analytics_paths() -> None:
    client = _client(AGG_FIXTURES)
    schema = client.get("/openapi.json").json()

    paths = schema["paths"]
    assert "/analytics/spending" in paths
    assert "/analytics/summary" in paths
    assert "/analytics/receipts" in paths

    spending_schema = paths["/analytics/spending"]["get"]["responses"]["200"][
        "content"
    ]["application/json"]["schema"]
    # Prefer component ref; resolve name for AggregationResponse
    ref = spending_schema.get("$ref", "")
    assert "AggregationResponse" in ref or "AggregationResponse" in str(schema)

    receipts_schema = paths["/analytics/receipts"]["get"]["responses"]["200"][
        "content"
    ]["application/json"]["schema"]
    ref = receipts_schema.get("$ref", "")
    assert "ReceiptCoverageResponse" in ref or "ReceiptCoverageResponse" in str(schema)
