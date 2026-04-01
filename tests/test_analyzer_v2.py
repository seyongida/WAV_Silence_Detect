"""AnalysisConfigV2 하위 호환 테스트."""

import os

import pytest

from analyzer import AnalysisConfigV2, run_analysis, validate_config


REF_PATH = os.path.join("sample_audio", "ref.wav")
DIF_PATH = os.path.join("sample_audio", "dif_2+shift.wav")


def test_v2_config_is_valid_analysis_config():
    """AnalysisConfigV2는 AnalysisConfig의 서브클래스."""
    from models import AnalysisConfig
    cfg = AnalysisConfigV2()
    assert isinstance(cfg, AnalysisConfig)
    assert validate_config(cfg) == []


def test_v2_run_analysis_works():
    if not (os.path.exists(REF_PATH) and os.path.exists(DIF_PATH)):
        pytest.skip("sample_audio/ref.wav or sample_audio/dif_2+shift.wav not present")
    cfg = AnalysisConfigV2()
    result = run_analysis(REF_PATH, DIF_PATH, cfg)
    assert result.ref_path == REF_PATH
    assert result.dif_path == DIF_PATH
