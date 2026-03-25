"""spectrum 모듈 속성 기반 테스트."""

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from models import AnalysisConfig
from spectrum import compute_all, compute_pitch


SR = 16000


def _make_config() -> AnalysisConfig:
    return AnalysisConfig(frame_ms=20, hop_ms=10)


def _make_sine(freq_hz: float, duration_sec: float, sr: int = SR) -> np.ndarray:
    """주어진 주파수의 사인파를 생성한다."""
    t = np.arange(int(sr * duration_sec)) / sr
    return (0.5 * np.sin(2 * np.pi * freq_hz * t)).astype(np.float32)


# ── Property 15: 피치 차이 유효 프레임 한정 ───────────────────────────────────

def test_property15_pitch_diff_valid_frames_only():
    """Feature: audio-quality-analyzer, Property 15: 피치 차이 유효 프레임 한정
    SpectrumData.mean_pitch_diff_hz는 ref/dif 모두 유효한 피치가 검출된 프레임만 기준으로 계산되어야 한다.
    Validates: Requirements 9.3
    """
    # 명확한 피치를 가진 신호 (200Hz 사인파)
    ref = _make_sine(200.0, 2.0)
    dif = _make_sine(210.0, 2.0)  # 10Hz 차이

    config = _make_config()
    result = compute_all(ref, dif, SR, config)

    ref_pitch = result.ref_pitch
    dif_pitch = result.dif_pitch

    # 유효 프레임 마스크
    min_len = min(len(ref_pitch), len(dif_pitch))
    valid_mask = ~(np.isnan(ref_pitch[:min_len]) | np.isnan(dif_pitch[:min_len]))

    if np.any(valid_mask):
        # mean_pitch_diff_hz가 유효 프레임만 기준으로 계산됐는지 검증
        expected = float(np.mean(np.abs(
            ref_pitch[:min_len][valid_mask] - dif_pitch[:min_len][valid_mask]
        )))
        assert abs(result.mean_pitch_diff_hz - expected) < 1e-3, (
            f"mean_pitch_diff_hz 불일치: {result.mean_pitch_diff_hz:.3f} != {expected:.3f}"
        )
    else:
        # 유효 프레임이 없으면 NaN이어야 함
        assert np.isnan(result.mean_pitch_diff_hz), (
            f"유효 프레임 없을 때 mean_pitch_diff_hz가 NaN이 아닙니다: {result.mean_pitch_diff_hz}"
        )


@settings(max_examples=30)
@given(
    ref_freq=st.floats(min_value=80.0, max_value=400.0, allow_nan=False),
    dif_freq=st.floats(min_value=80.0, max_value=400.0, allow_nan=False),
)
def test_property15_pitch_diff_nan_frames_excluded(ref_freq, dif_freq):
    """Feature: audio-quality-analyzer, Property 15: NaN 프레임 제외 검증
    mean_pitch_diff_hz 계산 시 NaN 프레임이 제외되어야 한다.
    Validates: Requirements 9.3
    """
    ref = _make_sine(ref_freq, 1.0)
    dif = _make_sine(dif_freq, 1.0)

    config = _make_config()
    result = compute_all(ref, dif, SR, config)

    ref_pitch = result.ref_pitch
    dif_pitch = result.dif_pitch
    min_len = min(len(ref_pitch), len(dif_pitch))

    valid_mask = ~(np.isnan(ref_pitch[:min_len]) | np.isnan(dif_pitch[:min_len]))

    if np.any(valid_mask):
        # NaN이 포함된 프레임이 계산에서 제외됐는지 확인
        # 유효 프레임만으로 계산한 값과 일치해야 함
        expected = float(np.mean(np.abs(
            ref_pitch[:min_len][valid_mask] - dif_pitch[:min_len][valid_mask]
        )))
        assert not np.isnan(result.mean_pitch_diff_hz), "유효 프레임이 있는데 NaN 반환"
        assert abs(result.mean_pitch_diff_hz - expected) < 1e-3
    else:
        assert np.isnan(result.mean_pitch_diff_hz)
