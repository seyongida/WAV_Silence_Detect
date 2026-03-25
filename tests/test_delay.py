"""delay 모듈 속성 기반 테스트."""

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from delay import apply_delay, estimate_delay_cc, refine_delay_dtw


SR = 16000  # 테스트용 샘플레이트


def _make_signal(n_samples: int, seed: int = 42) -> np.ndarray:
    """테스트용 랜덤 신호를 생성한다."""
    rng = np.random.default_rng(seed)
    return rng.uniform(-1.0, 1.0, n_samples).astype(np.float32)


def _shift_signal(sig: np.ndarray, delay_ms: float, sr: int) -> np.ndarray:
    """신호를 delay_ms만큼 이동시킨다 (양수=뒤로 밀기)."""
    shift = int(round(delay_ms / 1000.0 * sr))
    result = np.zeros_like(sig)
    if shift > 0:
        result[shift:] = sig[:len(sig) - shift]
    elif shift < 0:
        s = -shift
        result[:len(sig) - s] = sig[s:]
    else:
        result = sig.copy()
    return result


# ── Property 6: 지연 추정 정확도 (라운드 트립) ────────────────────────────────

@settings(max_examples=100)
@given(
    delay_ms=st.floats(min_value=-200.0, max_value=200.0, allow_nan=False, allow_infinity=False),
    seed=st.integers(min_value=0, max_value=9999),
)
def test_property6_delay_estimation_accuracy(delay_ms, seed):
    """Feature: audio-quality-analyzer, Property 6: 지연 추정 정확도 (라운드 트립)
    알려진 지연량 d(ms)로 이동시킨 신호에 대해 estimate_delay_cc()가 d ± 10ms 이내로 추정해야 한다.
    Validates: Requirements 4.1, 4.4
    """
    # 구조적 신호 생성: 임펄스 + 랜덤 노이즈로 cross-correlation이 명확하게 동작하도록
    rng = np.random.default_rng(seed)
    n_samples = SR * 3  # 3초 신호

    # 기저 신호: 랜덤 노이즈
    ref = rng.uniform(-0.5, 0.5, n_samples).astype(np.float32)

    # 임펄스를 중간에 삽입하여 cross-correlation 피크를 명확하게 만듦
    impulse_pos = n_samples // 2
    ref[impulse_pos] = 1.0
    ref[impulse_pos + 1] = -1.0

    # dif = ref를 delay_ms만큼 이동 (양수=dif가 늦음)
    dif = _shift_signal(ref, delay_ms, SR)

    estimated_ms = estimate_delay_cc(ref, dif, SR)

    tolerance_ms = 10.0
    assert abs(estimated_ms - delay_ms) <= tolerance_ms, (
        f"지연 추정 오차 초과: 실제={delay_ms:.1f}ms, 추정={estimated_ms:.1f}ms, "
        f"오차={abs(estimated_ms - delay_ms):.1f}ms > {tolerance_ms}ms"
    )
