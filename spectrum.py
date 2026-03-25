"""스펙트럼 분석 모듈 (Spectral Centroid, Rolloff, 피치, ZCR, 스펙트로그램)."""

import numpy as np
import scipy.signal as signal

from models import AnalysisConfig, SpectrogramData, SpectrumData


def compute_spectral_centroid(audio: np.ndarray, sr: int, config: AnalysisConfig) -> np.ndarray:
    """프레임별 Spectral Centroid 시계열(Hz)을 반환한다.

    매개변수:
        audio (np.ndarray): 오디오 신호
        sr (int): 샘플레이트 (Hz)
        config (AnalysisConfig): frame_ms, hop_ms 사용

    반환값:
        np.ndarray: Spectral Centroid 시계열 (Hz)
    """
    mono = _to_mono(audio)
    frame_len, hop_len = _frame_hop_len(sr, config)
    frames = _get_frames(mono, frame_len, hop_len)

    centroids = []
    freqs = np.fft.rfftfreq(frame_len, d=1.0 / sr)

    for frame in frames:
        windowed = frame * np.hanning(len(frame))
        spectrum = np.abs(np.fft.rfft(windowed, n=frame_len))
        total = np.sum(spectrum)
        if total > 0:
            centroid = float(np.sum(freqs * spectrum) / total)
        else:
            centroid = 0.0
        centroids.append(centroid)

    return np.array(centroids, dtype=np.float32)


def compute_spectral_rolloff(audio: np.ndarray, sr: int, config: AnalysisConfig,
                              rolloff_percent: float = 0.85) -> np.ndarray:
    """프레임별 Spectral Rolloff 시계열(Hz)을 반환한다.

    매개변수:
        audio (np.ndarray): 오디오 신호
        sr (int): 샘플레이트 (Hz)
        config (AnalysisConfig): frame_ms, hop_ms 사용
        rolloff_percent (float): 에너지 누적 비율 (기본값 0.85)

    반환값:
        np.ndarray: Spectral Rolloff 시계열 (Hz)
    """
    mono = _to_mono(audio)
    frame_len, hop_len = _frame_hop_len(sr, config)
    frames = _get_frames(mono, frame_len, hop_len)

    rolloffs = []
    freqs = np.fft.rfftfreq(frame_len, d=1.0 / sr)

    for frame in frames:
        windowed = frame * np.hanning(len(frame))
        spectrum = np.abs(np.fft.rfft(windowed, n=frame_len)) ** 2
        total = np.sum(spectrum)
        if total > 0:
            cumsum = np.cumsum(spectrum)
            threshold = rolloff_percent * total
            idx = np.searchsorted(cumsum, threshold)
            idx = min(idx, len(freqs) - 1)
            rolloff = float(freqs[idx])
        else:
            rolloff = 0.0
        rolloffs.append(rolloff)

    return np.array(rolloffs, dtype=np.float32)


def compute_pitch(audio: np.ndarray, sr: int, config: AnalysisConfig) -> np.ndarray:
    """프레임별 피치(Hz)를 반환한다. 미검출 프레임은 NaN.

    자기상관(autocorrelation) 기반 피치 추정을 사용한다.

    매개변수:
        audio (np.ndarray): 오디오 신호
        sr (int): 샘플레이트 (Hz)
        config (AnalysisConfig): frame_ms, hop_ms 사용

    반환값:
        np.ndarray: 피치 시계열 (Hz, NaN=미검출)
    """
    mono = _to_mono(audio)
    frame_len, hop_len = _frame_hop_len(sr, config)
    frames = _get_frames(mono, frame_len, hop_len)

    # 피치 범위: 50Hz ~ 500Hz
    min_period = int(sr / 500)
    max_period = int(sr / 50)

    pitches = []
    for frame in frames:
        pitch = _estimate_pitch_autocorr(frame, sr, min_period, max_period)
        pitches.append(pitch)

    return np.array(pitches, dtype=np.float32)


def compute_zcr(audio: np.ndarray, sr: int, config: AnalysisConfig) -> np.ndarray:
    """프레임별 ZCR 시계열을 반환한다.

    매개변수:
        audio (np.ndarray): 오디오 신호
        sr (int): 샘플레이트 (Hz)
        config (AnalysisConfig): frame_ms, hop_ms 사용

    반환값:
        np.ndarray: ZCR 시계열
    """
    mono = _to_mono(audio)
    frame_len, hop_len = _frame_hop_len(sr, config)
    frames = _get_frames(mono, frame_len, hop_len)

    zcrs = []
    for frame in frames:
        if len(frame) <= 1:
            zcrs.append(0.0)
            continue
        signs = np.sign(frame.astype(np.float32))
        crossings = np.sum(np.abs(np.diff(signs)) > 0)
        zcrs.append(float(crossings / (len(frame) - 1)))

    return np.array(zcrs, dtype=np.float32)


def compute_spectrogram(audio: np.ndarray, sr: int, config: AnalysisConfig) -> SpectrogramData:
    """스펙트로그램 데이터(주파수×시간 행렬, 주파수 축, 시간 축)를 반환한다.

    매개변수:
        audio (np.ndarray): 오디오 신호
        sr (int): 샘플레이트 (Hz)
        config (AnalysisConfig): frame_ms, hop_ms 사용

    반환값:
        SpectrogramData: magnitude_db, frequencies, times
    """
    mono = _to_mono(audio)
    frame_len, hop_len = _frame_hop_len(sr, config)

    freqs, times, Sxx = signal.spectrogram(
        mono,
        fs=sr,
        nperseg=frame_len,
        noverlap=frame_len - hop_len,
        window="hann",
        scaling="spectrum",
    )

    magnitude_db = 10.0 * np.log10(Sxx + 1e-10).astype(np.float32)

    return SpectrogramData(
        magnitude_db=magnitude_db,
        frequencies=freqs.astype(np.float32),
        times=times.astype(np.float32),
    )


def compute_all(
    ref: np.ndarray,
    dif_aligned: np.ndarray,
    sr: int,
    config: AnalysisConfig,
) -> SpectrumData:
    """ref와 dif_aligned에 대한 전체 스펙트럼 분석을 수행하고 SpectrumData를 반환한다.

    분석 실패 시 예외를 발생시키며, 호출자(run_analysis)가 이를 받아 spectrum=None 처리 및
    warn 로그를 기록한다.

    매개변수:
        ref (np.ndarray): 기준 신호
        dif_aligned (np.ndarray): 지연 보정 후 정렬된 dif 신호
        sr (int): 샘플레이트 (Hz)
        config (AnalysisConfig): 분석 파라미터

    반환값:
        SpectrumData: 전체 스펙트럼 분석 결과
    """
    ref_centroid = compute_spectral_centroid(ref, sr, config)
    dif_centroid = compute_spectral_centroid(dif_aligned, sr, config)
    ref_rolloff = compute_spectral_rolloff(ref, sr, config)
    dif_rolloff = compute_spectral_rolloff(dif_aligned, sr, config)
    ref_pitch = compute_pitch(ref, sr, config)
    dif_pitch = compute_pitch(dif_aligned, sr, config)
    ref_zcr = compute_zcr(ref, sr, config)
    dif_zcr = compute_zcr(dif_aligned, sr, config)
    ref_spectrogram = compute_spectrogram(ref, sr, config)
    dif_spectrogram = compute_spectrogram(dif_aligned, sr, config)

    # mean_pitch_diff_hz: ref/dif 모두 유효한 피치가 검출된 프레임만 기준
    min_len = min(len(ref_pitch), len(dif_pitch))
    ref_p = ref_pitch[:min_len]
    dif_p = dif_pitch[:min_len]
    valid_mask = ~(np.isnan(ref_p) | np.isnan(dif_p))

    if np.any(valid_mask):
        mean_pitch_diff_hz = float(np.mean(np.abs(ref_p[valid_mask] - dif_p[valid_mask])))
    else:
        mean_pitch_diff_hz = float("nan")

    return SpectrumData(
        ref_centroid=ref_centroid,
        dif_centroid=dif_centroid,
        ref_rolloff=ref_rolloff,
        dif_rolloff=dif_rolloff,
        ref_pitch=ref_pitch,
        dif_pitch=dif_pitch,
        mean_pitch_diff_hz=mean_pitch_diff_hz,
        ref_zcr=ref_zcr,
        dif_zcr=dif_zcr,
        ref_spectrogram=ref_spectrogram,
        dif_spectrogram=dif_spectrogram,
    )


# ── 내부 헬퍼 ─────────────────────────────────────────────────────────────────

def _to_mono(audio: np.ndarray) -> np.ndarray:
    """다채널 신호를 모노로 변환한다."""
    if audio.ndim == 1:
        return audio.astype(np.float32)
    return audio.mean(axis=1).astype(np.float32)


def _frame_hop_len(sr: int, config: AnalysisConfig) -> tuple[int, int]:
    """frame_len과 hop_len을 샘플 단위로 반환한다."""
    frame_len = max(1, int(sr * config.frame_ms / 1000))
    hop_len = max(1, int(sr * config.hop_ms / 1000))
    return frame_len, hop_len


def _get_frames(mono: np.ndarray, frame_len: int, hop_len: int) -> list[np.ndarray]:
    """신호를 프레임 목록으로 분할한다."""
    frames = []
    idx = 0
    while idx + frame_len <= len(mono):
        frames.append(mono[idx: idx + frame_len])
        idx += hop_len
    return frames


def _estimate_pitch_autocorr(
    frame: np.ndarray,
    sr: int,
    min_period: int,
    max_period: int,
) -> float:
    """자기상관 기반 피치 추정. 미검출 시 NaN 반환."""
    if len(frame) < max_period * 2:
        return float("nan")

    # 자기상관 계산
    frame_d = frame.astype(np.float64)
    corr = np.correlate(frame_d, frame_d, mode="full")
    corr = corr[len(corr) // 2:]  # 양의 lag만

    if max_period >= len(corr):
        return float("nan")

    # 탐색 범위 내 최대값
    search = corr[min_period: max_period + 1]
    if len(search) == 0:
        return float("nan")

    peak_idx = int(np.argmax(search)) + min_period

    # 신뢰도 검사: 피크가 0번 lag의 일정 비율 이상이어야 함
    if corr[0] <= 0:
        return float("nan")
    confidence = corr[peak_idx] / corr[0]
    if confidence < 0.3:
        return float("nan")

    return float(sr / peak_idx)
