"""metrics 모듈 속성 기반 테스트."""

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from metrics import (
    compute_clipping,
    compute_noise_floor,
    compute_pesq,
    compute_rms_diff,
    compute_snr,
    compute_stoi,
)
from models import AnalysisConfig


SR = 16000


def _make_signal(n_samples: int, seed: int = 42, amplitude: float = 0.5) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return (rng.uniform(-amplitude, amplitude, n_samples)).astype(np.float32)


# ── Property 11: SNR 동일 신호 상한 ───────────────────────────────────────────

def test_property11_snr_identical_signals():
    """Feature: audio-quality-analyzer, Property 11: SNR 동일 신호 상한
    ref == dif인 경우 compute_snr()은 100 dB 초과 값을 반환해야 한다.
    Validates: Requirements 8.1
    """
    ref = _make_signal(SR * 2)
    snr = compute_snr(ref, ref.copy())
    assert snr > 100.0, f"동일 신호 SNR이 100dB 이하입니다: {snr:.1f}dB"


@settings(max_examples=100)
@given(
    n_samples=st.integers(min_value=100, max_value=8000),
    seed=st.integers(min_value=0, max_value=9999),
)
def test_property11_snr_identical_signals_property(n_samples, seed):
    """Feature: audio-quality-analyzer, Property 11: SNR 동일 신호 상한 (속성 기반)
    임의 신호에서 ref == dif이면 SNR > 100 dB이어야 한다.
    Validates: Requirements 8.1
    """
    ref = _make_signal(n_samples, seed=seed)
    snr = compute_snr(ref, ref.copy())
    assert snr > 100.0, f"동일 신호 SNR이 100dB 이하입니다: {snr:.1f}dB"


# ── Property 12: PESQ 점수 범위 ───────────────────────────────────────────────

@settings(max_examples=20)
@given(
    seed=st.integers(min_value=0, max_value=999),
)
def test_property12_pesq_score_range(seed):
    """Feature: audio-quality-analyzer, Property 12: PESQ 점수 범위
    compute_pesq()가 None이 아닌 값을 반환할 때 [1.0, 4.5] 범위이어야 한다.
    Validates: Requirements 8.2
    """
    rng = np.random.default_rng(seed)
    # 16kHz, 3초 신호
    ref = rng.uniform(-0.5, 0.5, SR * 3).astype(np.float32)
    dif = ref + rng.uniform(-0.1, 0.1, len(ref)).astype(np.float32)
    dif = np.clip(dif, -1.0, 1.0).astype(np.float32)

    score = compute_pesq(ref, dif, SR)
    if score is not None:
        assert 1.0 <= score <= 4.5, f"PESQ 점수 범위 초과: {score}"


# ── Property 13: STOI 점수 범위 ───────────────────────────────────────────────

@settings(max_examples=20)
@given(
    seed=st.integers(min_value=0, max_value=999),
)
def test_property13_stoi_score_range(seed):
    """Feature: audio-quality-analyzer, Property 13: STOI 점수 범위
    compute_stoi()가 None이 아닌 값을 반환할 때 [0.0, 1.0] 범위이어야 한다.
    Validates: Requirements 8.3
    """
    rng = np.random.default_rng(seed)
    ref = rng.uniform(-0.5, 0.5, SR * 3).astype(np.float32)
    dif = ref + rng.uniform(-0.1, 0.1, len(ref)).astype(np.float32)
    dif = np.clip(dif, -1.0, 1.0).astype(np.float32)

    score = compute_stoi(ref, dif, SR)
    if score is not None:
        assert 0.0 <= score <= 1.0, f"STOI 점수 범위 초과: {score}"


# ── Property 14: Clipping 비율 계산 정확도 ────────────────────────────────────

@settings(max_examples=100)
@given(
    n_total=st.integers(min_value=10, max_value=1000),
    n_clipped=st.integers(min_value=0, max_value=10),
    seed=st.integers(min_value=0, max_value=9999),
)
def test_property14_clipping_ratio_accuracy(n_total, n_clipped, seed):
    """Feature: audio-quality-analyzer, Property 14: Clipping 비율 계산 정확도
    알려진 클리핑 샘플 수를 가진 신호로 compute_clipping() 반환값이
    (클리핑 샘플 수 / 전체 샘플 수)와 일치해야 한다.
    Validates: Requirements 8.5
    """
    n_clipped = min(n_clipped, n_total)
    rng = np.random.default_rng(seed)

    # 비클리핑 신호 (0.998 미만)
    audio = rng.uniform(-0.998, 0.998, n_total).astype(np.float32)

    # 정확히 n_clipped개 샘플을 클리핑 값으로 설정
    if n_clipped > 0:
        clip_indices = rng.choice(n_total, size=n_clipped, replace=False)
        audio[clip_indices] = 1.0  # >= 0.999

    ratio = compute_clipping(audio)
    expected = n_clipped / n_total

    assert abs(ratio - expected) < 1e-6, (
        f"Clipping 비율 불일치: {ratio:.6f} != {expected:.6f} "
        f"(클리핑={n_clipped}, 전체={n_total})"
    )
