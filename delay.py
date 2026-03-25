"""지연 보정 모듈 (Cross-correlation 및 DTW 기반)."""

import numpy as np
import scipy.signal as signal
import scipy.spatial.distance as dist


def estimate_delay_cc(ref: np.ndarray, dif: np.ndarray, sr: int) -> float:
    """Cross-correlation 기반 전체 지연량(ms)을 추정한다.

    Cross-correlation을 적용하여 전체 지연량을 추정한다.
    양수 값은 dif가 ref보다 늦음을 의미한다.

    매개변수:
        ref (np.ndarray): 기준 신호 (1D float32)
        dif (np.ndarray): 비교 신호 (1D float32)
        sr (int): 샘플레이트 (Hz)

    반환값:
        float: 추정된 coarse 지연량 (ms). 양수=dif 지연, 음수=dif 앞섬
    """
    ref_mono = _to_mono(ref)
    dif_mono = _to_mono(dif)

    # scipy.signal.correlate: correlate(dif, ref)에서
    # lag > 0 이면 dif가 ref보다 늦음 (dif가 지연됨)
    correlation = signal.correlate(dif_mono, ref_mono, mode="full")
    lags = signal.correlation_lags(len(dif_mono), len(ref_mono), mode="full")

    peak_idx = int(np.argmax(correlation))
    lag_samples = int(lags[peak_idx])

    delay_ms = lag_samples / sr * 1000.0
    return float(delay_ms)


def refine_delay_dtw(
    ref: np.ndarray,
    dif: np.ndarray,
    sr: int,
    coarse_delay_ms: float,
) -> float:
    """coarse_delay_ms 기준 ±500ms 윈도우 내에서 DTW로 세부 지연 보정량(ms)을 추정한다.

    DTW는 지연량 추정에만 사용하며, 비선형 워핑은 신호에 적용하지 않는다.

    매개변수:
        ref (np.ndarray): 기준 신호 (1D float32)
        dif (np.ndarray): 비교 신호 (1D float32)
        sr (int): 샘플레이트 (Hz)
        coarse_delay_ms (float): Cross-correlation으로 추정한 coarse 지연량 (ms)

    반환값:
        float: 세부 보정된 지연량 (ms)
    """
    ref_mono = _to_mono(ref)
    dif_mono = _to_mono(dif)

    # ±500ms 윈도우 샘플 수
    window_samples = int(0.5 * sr)
    coarse_samples = int(coarse_delay_ms / 1000.0 * sr)

    # dif에서 coarse 지연 기준 윈도우 추출
    dif_start = max(0, coarse_samples - window_samples)
    dif_end = min(len(dif_mono), coarse_samples + window_samples)

    # ref 윈도우 (동일 길이)
    ref_len = dif_end - dif_start
    ref_start = 0
    ref_end = min(len(ref_mono), ref_len)

    ref_win = ref_mono[ref_start:ref_end]
    dif_win = dif_mono[dif_start:dif_end]

    if len(ref_win) < 2 or len(dif_win) < 2:
        return coarse_delay_ms

    # 다운샘플링 (DTW 계산 비용 절감)
    target_sr = min(sr, 4000)
    factor = max(1, sr // target_sr)
    ref_ds = ref_win[::factor]
    dif_ds = dif_win[::factor]
    ds_sr = sr // factor

    # DTW로 최적 정렬 지점 찾기
    dtw_lag = _dtw_lag(ref_ds, dif_ds)
    dtw_lag_ms = dtw_lag / ds_sr * 1000.0

    # coarse + DTW 보정량
    refined_ms = coarse_delay_ms + dtw_lag_ms
    return float(refined_ms)


def apply_delay(dif: np.ndarray, delay_ms: float, sr: int) -> np.ndarray:
    """지연 보정을 적용한 정렬된 dif 신호를 반환한다.

    단일 시간축 shift를 적용한다. 양수 delay_ms이면 dif를 앞으로 당기고,
    음수이면 뒤로 민다.

    매개변수:
        dif (np.ndarray): 비교 신호
        delay_ms (float): 적용할 지연량 (ms). 양수=dif 지연(앞으로 당김), 음수=dif 앞섬(뒤로 밀기)
        sr (int): 샘플레이트 (Hz)

    반환값:
        np.ndarray: 정렬된 dif 신호 (원본과 동일한 shape)
    """
    shift_samples = int(round(delay_ms / 1000.0 * sr))

    if shift_samples == 0:
        return dif.copy()

    result = np.zeros_like(dif)

    if dif.ndim == 1:
        if shift_samples > 0:
            # dif를 앞으로 당김 (shift_samples 이후부터 복사)
            result[:len(dif) - shift_samples] = dif[shift_samples:]
        else:
            # dif를 뒤로 밀기
            s = -shift_samples
            result[s:] = dif[:len(dif) - s]
    else:
        if shift_samples > 0:
            result[:len(dif) - shift_samples] = dif[shift_samples:]
        else:
            s = -shift_samples
            result[s:] = dif[:len(dif) - s]

    return result


# ── 내부 헬퍼 ─────────────────────────────────────────────────────────────────

def _to_mono(audio: np.ndarray) -> np.ndarray:
    """다채널 신호를 모노로 변환한다."""
    if audio.ndim == 1:
        return audio.astype(np.float32)
    return audio.mean(axis=1).astype(np.float32)


def _dtw_lag(ref: np.ndarray, dif: np.ndarray) -> int:
    """DTW 경로에서 평균 lag(샘플)를 추정한다."""
    n, m = len(ref), len(dif)
    # DTW 비용 행렬
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

    # 역추적으로 경로 복원
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
