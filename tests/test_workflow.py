from __future__ import annotations

from pathlib import Path

from specdrift_local.dashboard import build_dashboard
from specdrift_local.runner import init_demo, score_suite, verify_outputs
from specdrift_local.scorer import correlation, suggest_patches
from specdrift_local.specs import load_specs


def test_patch_suggester_detects_asymmetric_drift() -> None:
    api = next(item for item in load_specs() if item.id == "network-qos")
    patches = suggest_patches(api)
    assert any("application_id" in patch.issue for patch in patches)
    assert any("Response schema" in patch.issue for patch in patches)


def test_correlation_helper() -> None:
    assert correlation([1, 2, 3], [2, 4, 6]) == 1.0


def test_end_to_end_score_and_verify() -> None:
    init_demo(force=True)
    summary = score_suite(iterations=20)
    report = verify_outputs()
    assert summary.api_count == 5
    assert summary.aci_human_correlation >= 0.85
    assert report["passed"] is True


def test_outputs_include_patches_and_mcp_descriptors() -> None:
    init_demo(force=True)
    score_suite(iterations=20)
    root = Path(__file__).resolve().parents[1]
    assert len(list((root / "outputs" / "patches").glob("*.json"))) >= 5
    assert len(list((root / "outputs" / "mcp").glob("*.json"))) == 5


def test_dashboard_contains_mode_comparison() -> None:
    init_demo(force=True)
    score_suite(iterations=20)
    html = Path(build_dashboard()).read_text(encoding="utf-8")
    assert "Mode Comparison" in html
    assert "Verification passed" in html
