"""음질 지표 계산 모듈 (SNR, PESQ, STOI, RMS, Clipping, Noise Floor)."""

import logging
import numpy as np
import scipy.signal as signal

from models import AnalysisConfig

logger = logging.getLogger(__name__)


def extract_common_segment(
    ref: np.ndarray,
    dif_aligned: np.ndarray,
    sr: int,
) -> tuple[np.ndarray, np.ndarray]:
    """지연 보정 후 시간적으로 겹치는 공통 구간(ref_common, dif_common)을 추출하여 반환한다.

    매개변수:
        ref (np.ndarray): 기준 신호
        dif_aligned (np.ndarray): 지연 보정 후 정렬된 dif 신호
        sr (int): 샘플레이트 (Hz)

    반환값:
        tuple[np.ndarray, np.ndarray]: (ref_common, dif_common) — 동일 길이의 공통 구간 신호
    """
    min_len = min(len(ref), len(dif_aligned))
    ref_common = ref[:min_len].copy()
    dif_common = dif_aligned[:min_len].copy()

    # 모노 변환
    if ref_common.ndim > 1:
        ref_common = ref_common.mean(axis=1).astype(np.float32)
    if dif_common.ndim > 1:
        dif_common = dif_common.mean(axis=1).astype(np.float32)

    return ref_common, dif_common


def compute_snr(ref_common: np.ndarray, dif_common: np.ndarray) -> float:
    """지연 보정 후 공통 구간(ref_common, dif_common)만을 입력으로 받아 SNR(dB)을 계산한다.

    SNR = 10 * log10(sum(ref^2) / sum((ref - dif)^2))

    매개변수:
        ref_common (np.ndarray): ref 공통 구간
        dif_common (np.ndarray): dif 공통 구간

    반환값:
        float: SNR (dB)
    """
    ref_power = float(np.sum(ref_common.astype(np.float64) ** 2))
    noise = ref_common.astype(np.float64) - dif_common.astype(np.float64)
    noise_power = float(np.sum(noise ** 2))

    if noise_power <= 0:
        return 200.0  # 동일 신호 → 매우 높은 SNR (100dB 초과 보장)
    if ref_power <= 0:
        return -100.0

    return float(10.0 * np.log10(ref_power / noise_power))


def compute_pesq(
    ref_common: np.ndarray,
    dif_common: np.ndarray,
    sr: int,
) -> float | None:
    """지연 보정 후 공통 구간(ref_common, dif_common)을 입력으로 받아 PESQ MOS-LQO 점수를 계산한다.

    48kHz 입력은 내부적으로 16kHz로 리샘플링하여 광대역 모드로 처리한다.

    매개변수:
        ref_common (np.ndarray): ref 공통 구간
        dif_common (np.ndarray): dif 공통 구간
        sr (int): 샘플레이트 (Hz)

    반환값:
        float | None: PESQ MOS-LQO [1.0, 4.5], 계산 불가 시 None
    """
    try:
        from pesq import pesq as pesq_fn
    except ImportError:
        logger.warning("pesq 라이브러리가 설치되지 않았습니다. PESQ 지표를 계산할 수 없습니다.")
        return None

    try:
        ref_f = ref_common.astype(np.float32)
        dif_f = dif_common.astype(np.float32)

        # PESQ는 8kHz(협대역) 또는 16kHz(광대역)만 지원
        if sr not in (8000, 16000):
            target_sr = 16000
            n_out = int(len(ref_f) * target_sr / sr)
            ref_f = signal.resample(ref_f, n_out).astype(np.float32)
            dif_f = signal.resample(dif_f, n_out).astype(np.float32)
            pesq_sr = target_sr
        else:
            pesq_sr = sr

        mode = "wb" if pesq_sr == 16000 else "nb"
        score = pesq_fn(pesq_sr, ref_f, dif_f, mode)
        return float(score)
    except Exception as e:
        logger.warning(f"PESQ 계산 실패: {e}")
        return None


def compute_stoi(
    ref_common: np.ndarray,
    dif_common: np.ndarray,
    sr: int,
) -> float | None:
    """지연 보정 후 공통 구간(ref_common, dif_common)을 입력으로 받아 STOI 음성 명료도 지수를 계산한다.

    매개변수:
        ref_common (np.ndarray): ref 공통 구간
        dif_common (np.ndarray): dif 공통 구간
        sr (int): 샘플레이트 (Hz)

    반환값:
        float | None: STOI [0.0, 1.0], 계산 불가 시 None
    """
    try:
        from pystoi import stoi as stoi_fn
    except ImportError:
        logger.warning("pystoi 라이브러리가 설치되지 않았습니다. STOI 지표를 계산할 수 없습니다.")
        return None

    try:
        score = stoi_fn(
            ref_common.astype(np.float64),
            dif_common.astype(np.float64),
            sr,
            extended=False,
        )
        return float(np.clip(score, 0.0, 1.0))
    except Exception as e:
        logger.warning(f"STOI 계산 실패: {e}")
        return None


def compute_rms_diff(ref_common: np.ndarray, dif_common: np.ndarray) -> float:
    """공통 구간(ref_common, dif_common) 기준 RMS 에너지 차이(dB)를 반환한다.

    매개변수:
        ref_common (np.ndarray): ref 공통 구간
        dif_common (np.ndarray): dif 공통 구간

    반환값:
        float: RMS 에너지 차이 (dB, dif - ref 기준)
    """
    ref_rms = float(np.sqrt(np.mean(ref_common.astype(np.float64) ** 2)))
    dif_rms = float(np.sqrt(np.mean(dif_common.astype(np.float64) ** 2)))

    eps = 1e-10
    return float(20.0 * np.log10((dif_rms + eps) / (ref_rms + eps)))


def compute_clipping(audio: np.ndarray) -> float:
    """진폭이 ±1.0의 99.9% 이상인 샘플 비율(클리핑 비율)을 반환한다.

    실제 음원의 Peak가 0.9999 수준으로 높아 99% 기준 시 오탐 가능성이 있으므로 99.9% 기준 적용.

    매개변수:
        audio (np.ndarray): 오디오 신호

    반환값:
        float: 클리핑 비율 [0.0, 1.0]
    """
    threshold = 0.999
    clipped = np.sum(np.abs(audio.astype(np.float64)) >= threshold)
    return float(clipped / max(len(audio.flatten()), 1))


def compute_noise_floor(audio: np.ndarray, sr: int, config: AnalysisConfig) -> float:
    """프레임별 log-energy 하위 percentile 기반 배경 잡음 레벨(dB)을 추정한다.

    매개변수:
        audio (np.ndarray): 오디오 신호
        sr (int): 샘플레이트 (Hz)
        config (AnalysisConfig): noise_floor_percentile 사용

    반환값:
        float: 배경 잡음 레벨 (dB)
    """
    mono = audio if audio.ndim == 1 else audio.mean(axis=1).astype(np.float32)
    frame_len = int(sr * config.frame_ms / 1000)
    if frame_len <= 0:
        frame_len = 160

    energies = []
    for i in range(0, len(mono) - frame_len + 1, frame_len):
        frame = mono[i: i + frame_len].astype(np.float64)
        energy = np.sum(frame ** 2)
        if energy > 0:
            energies.append(10.0 * np.log10(energy + 1e-10))
        else:
            energies.append(-100.0)

    if not energies:
        return -100.0

    return float(np.percentile(energies, config.noise_floor_percentile))
