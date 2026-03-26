"""Delay estimation/alignment utilities (cross-correlation + DTW refinement)."""

import numpy as np
import scipy.signal as signal


def estimate_delay_cc(ref: np.ndarray, dif: np.ndarray, sr: int) -> float:
    """Estimate coarse delay in milliseconds using cross-correlation.

    Positive delay means `dif` is delayed relative to `ref`.
    """
    ref_mono = _to_mono(ref)
    dif_mono = _to_mono(dif)

    corr = signal.correlate(dif_mono, ref_mono, mode="full")
    lags = signal.correlation_lags(len(dif_mono), len(ref_mono), mode="full")
    lag_samples = int(lags[int(np.argmax(corr))])
    return float(lag_samples / sr * 1000.0)


def refine_delay_dtw(
    ref: np.ndarray,
    dif: np.ndarray,
    sr: int,
    coarse_delay_ms: float,
) -> float:
    """Refine delay around a bounded local window with DTW lag."""
    ref_mono = _to_mono(ref)
    dif_mono = _to_mono(dif)

    window_samples = int(0.5 * sr)
    coarse_samples = int(coarse_delay_ms / 1000.0 * sr)

    # Build bounded paired windows to avoid pathological huge DTW matrices.
    if coarse_samples >= 0:
        dif_center = coarse_samples
        ref_center = 0
    else:
        dif_center = 0
        ref_center = -coarse_samples

    dif_start = max(0, dif_center - window_samples)
    dif_end = min(len(dif_mono), dif_center + window_samples)
    ref_start = max(0, ref_center - window_samples)
    ref_end = min(len(ref_mono), ref_center + window_samples)

    if dif_end <= dif_start or ref_end <= ref_start:
        return coarse_delay_ms

    win_len = min(dif_end - dif_start, ref_end - ref_start)
    dif_end = dif_start + win_len
    ref_end = ref_start + win_len

    ref_win = ref_mono[ref_start:ref_end]
    dif_win = dif_mono[dif_start:dif_end]

    if len(ref_win) < 2 or len(dif_win) < 2:
        return coarse_delay_ms

    target_sr = min(sr, 4000)
    factor = max(1, sr // target_sr)
    ref_ds = ref_win[::factor]
    dif_ds = dif_win[::factor]
    ds_sr = sr // factor

    dtw_lag = _dtw_lag(ref_ds, dif_ds)
    dtw_lag_ms = dtw_lag / ds_sr * 1000.0
    return float(coarse_delay_ms + dtw_lag_ms)


def apply_delay(dif: np.ndarray, delay_ms: float, sr: int) -> np.ndarray:
    """Apply integer-sample shift to `dif` and zero-pad the uncovered region."""
    n = dif.shape[0]
    shift_samples = int(round(delay_ms / 1000.0 * sr))

    if shift_samples == 0:
        return dif.copy()

    # shift가 신호 길이 이상이면 전체 제로 반환
    if abs(shift_samples) >= n:
        return np.zeros_like(dif)

    result = np.zeros_like(dif)

    if shift_samples > 0:
        result[: n - shift_samples] = dif[shift_samples:]
    else:
        s = -shift_samples
        result[s:] = dif[: n - s]
    return result


def _to_mono(audio: np.ndarray) -> np.ndarray:
    if audio.ndim == 1:
        return audio.astype(np.float32)
    return audio.mean(axis=1).astype(np.float32)


def _dtw_lag(ref: np.ndarray, dif: np.ndarray) -> int:
    """Estimate median lag from DTW path."""
    n, m = len(ref), len(dif)
    dtw_matrix = np.full((n + 1, m + 1), np.inf)
    dtw_matrix[0, 0] = 0.0

    for i in range(1, n + 1):
        for j in range(1, m + 1):
            cost = abs(float(ref[i - 1]) - float(dif[j - 1]))
            dtw_matrix[i, j] = cost + min(
                dtw_matrix[i - 1, j],
                dtw_matrix[i, j - 1],
                dtw_matrix[i - 1, j - 1],
            )

    i, j = n, m
    lags = []
    while i > 0 and j > 0:
        lags.append(j - i)
        candidates = [
            (dtw_matrix[i - 1, j - 1], i - 1, j - 1),
            (dtw_matrix[i - 1, j], i - 1, j),
            (dtw_matrix[i, j - 1], i, j - 1),
        ]
        _, i, j = min(candidates, key=lambda x: x[0])

    return int(np.median(lags)) if lags else 0
