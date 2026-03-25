"""Tests for analyzer (merged v2) config behavior."""

import os

import pytest

from analyzer import AnalysisConfigV2, run_analysis, validate_config

REF_PATH = os.path.join("sample_audio", "ref.wav")
DIF_PATH = os.path.join("sample_audio", "dif_2+shift.wav")


def test_v2_config_validation_rejects_non_positive_overlay_thresholds():
    cfg = AnalysisConfigV2(
        residual_diff_threshold=0.0,
        centroid_diff_threshold_hz=-1.0,
        rolloff_diff_threshold_hz=0.0,
    )
    errors = validate_config(cfg)
    assert any("residual_diff_threshold" in e for e in errors)
    assert any("centroid_diff_threshold_hz" in e for e in errors)
    assert any("rolloff_diff_threshold_hz" in e for e in errors)


def test_v2_run_analysis_preserves_overlay_thresholds_in_result_config():
    if not (os.path.exists(REF_PATH) and os.path.exists(DIF_PATH)):
        pytest.skip("sample_audio/ref.wav or sample_audio/dif_2+shift.wav not present")
    cfg = AnalysisConfigV2(
        residual_diff_threshold=0.07,
        centroid_diff_threshold_hz=250.0,
        rolloff_diff_threshold_hz=700.0,
    )
    result = run_analysis(REF_PATH, DIF_PATH, cfg)
    assert getattr(result.config, "residual_diff_threshold") == 0.07
    assert getattr(result.config, "centroid_diff_threshold_hz") == 250.0
    assert getattr(result.config, "rolloff_diff_threshold_hz") == 700.0
