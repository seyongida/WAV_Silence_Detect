"""음량 정규화 잔차(Volume-Normalized Residual) 로직 테스트.

ref와 dif가 볼륨 차이만 있을 때, 음량 정규화 후 잔차가 0이 되는지 검증한다.
볼륨 차이(dB) 계산도 함께 검증한다.
"""

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st


def compute_volume_normalized_residual(
    ref: np.ndarray, dif: np.ndarray
) -> tuple[np.ndarray, float, float]:
    """main.py _redraw 내부 음량 정규화 잔차 로직과 동일한 순수 함수.

    Returns:
        (residual, gain, vol_diff_db)
    """
    ref_rms = np.sqrt(np.mean(ref ** 2))
    dif_rms = np.sqrt(np.mean(dif ** 2))
    if dif_rms > 1e-12:
        gain = ref_rms / dif_rms
    else:
        gain = 1.0
    dif_scaled = dif * gain
    residual = ref - dif_scaled
    if ref_rms > 1e-12 and dif_rms > 1e-12:
        vol_diff_db = 20 * np.log10(dif_rms / ref_rms)
    else:
        vol_diff_db = 0.0
    return residual, gain, vol_diff_db


class TestVolumeNormalizedResidual:
    """음량 정규화 잔차 기본 동작 테스트."""

    def test_identical_signals_zero_residual(self):
        """동일 신호 → 잔차 0, 볼륨 차이 0 dB."""
        sig = np.sin(2 * np.pi * 440 * np.arange(16000) / 16000).astype(np.float32)
        residual, gain, vol_db = compute_volume_normalized_residual(sig, sig)
        assert np.allclose(residual, 0, atol=1e-6)
        assert abs(gain - 1.0) < 1e-6
        assert abs(vol_db) < 1e-6

    def test_volume_only_difference_zero_residual(self):
        """볼륨만 다른 신호 → 정규화 후 잔차 0, dB 정확."""
        t = np.arange(16000) / 16000
        ref = np.sin(2 * np.pi * 440 * t).astype(np.float64)
        dif = ref * 0.5  # 절반 볼륨
        residual, gain, vol_db = compute_volume_normalized_residual(ref, dif)
        assert np.allclose(residual, 0, atol=1e-10)
        assert abs(gain - 2.0) < 1e-6
        # 0.5배 → -6.02 dB
        assert abs(vol_db - 20 * np.log10(0.5)) < 0.01

    def test_volume_amplified_difference_zero_residual(self):
        """볼륨이 증폭된 신호 → 정규화 후 잔차 0, dB 양수."""
        t = np.arange(16000) / 16000
        ref = np.sin(2 * np.pi * 440 * t).astype(np.float64)
        dif = ref * 3.0  # 3배 볼륨
        residual, gain, vol_db = compute_volume_normalized_residual(ref, dif)
        assert np.allclose(residual, 0, atol=1e-10)
        assert abs(gain - 1.0 / 3.0) < 1e-6
        # 3배 → +9.54 dB
        assert abs(vol_db - 20 * np.log10(3.0)) < 0.01

    def test_different_waveform_nonzero_residual(self):
        """파형 자체가 다르면 잔차 != 0."""
        t = np.arange(16000) / 16000
        ref = np.sin(2 * np.pi * 440 * t)
        dif = np.sin(2 * np.pi * 880 * t)  # 다른 주파수
        residual, _, vol_db = compute_volume_normalized_residual(ref, dif)
        assert not np.allclose(residual, 0, atol=1e-3)
        # 동일 RMS 사인파 → 볼륨 차이 ≈ 0 dB
        assert abs(vol_db) < 0.5

    def test_silent_dif_gain_fallback(self):
        """dif가 무음이면 gain=1.0 폴백, vol_diff_db=0."""
        ref = np.sin(2 * np.pi * 440 * np.arange(16000) / 16000)
        dif = np.zeros(16000)
        residual, gain, vol_db = compute_volume_normalized_residual(ref, dif)
        assert gain == 1.0
        assert vol_db == 0.0
        assert np.allclose(residual, ref)

    def test_both_silent_zero_residual(self):
        """양쪽 모두 무음 → 잔차 0, vol_diff_db=0."""
        ref = np.zeros(16000)
        dif = np.zeros(16000)
        residual, gain, vol_db = compute_volume_normalized_residual(ref, dif)
        assert np.allclose(residual, 0)
        assert gain == 1.0
        assert vol_db == 0.0

    def test_noise_with_volume_diff_near_zero(self):
        """랜덤 노이즈에 볼륨 차이만 적용 → 잔차 ≈ 0, dB 정확."""
        rng = np.random.default_rng(42)
        ref = rng.standard_normal(16000)
        scale = 0.3
        dif = ref * scale
        residual, gain, vol_db = compute_volume_normalized_residual(ref, dif)
        assert np.allclose(residual, 0, atol=1e-10)
        assert abs(gain - 1.0 / scale) < 1e-4
        assert abs(vol_db - 20 * np.log10(scale)) < 0.01

    def test_vol_diff_db_sign_convention(self):
        """dB 부호 규칙: dif가 ref보다 크면 양수, 작으면 음수."""
        t = np.arange(16000) / 16000
        ref = np.sin(2 * np.pi * 440 * t)
        # dif가 ref보다 큰 경우
        _, _, vol_db_loud = compute_volume_normalized_residual(ref, ref * 2.0)
        assert vol_db_loud > 0
        # dif가 ref보다 작은 경우
        _, _, vol_db_quiet = compute_volume_normalized_residual(ref, ref * 0.25)
        assert vol_db_quiet < 0


class TestVolumeNormalizedResidualPBT:
    """Hypothesis 기반 속성 테스트."""

    @given(
        scale=st.floats(min_value=0.01, max_value=100.0),
        freq=st.floats(min_value=20.0, max_value=7900.0),
    )
    @settings(max_examples=50)
    def test_any_positive_scale_zero_residual(self, scale: float, freq: float):
        """임의 양수 스케일 × 동일 파형 → 정규화 후 잔차 ≈ 0."""
        t = np.arange(4000) / 16000
        ref = np.sin(2 * np.pi * freq * t)
        dif = ref * scale
        residual, _, vol_db = compute_volume_normalized_residual(ref, dif)
        assert np.allclose(residual, 0, atol=1e-6)
        expected_db = 20 * np.log10(scale)
        assert abs(vol_db - expected_db) < 0.1

    @given(scale=st.floats(min_value=0.01, max_value=100.0))
    @settings(max_examples=30)
    def test_vol_diff_db_matches_scale(self, scale: float):
        """vol_diff_db = 20*log10(scale) 관계 검증."""
        t = np.arange(4000) / 16000
        ref = np.sin(2 * np.pi * 440 * t)
        dif = ref * scale
        _, _, vol_db = compute_volume_normalized_residual(ref, dif)
        expected_db = 20 * np.log10(scale)
        assert abs(vol_db - expected_db) < 0.01
