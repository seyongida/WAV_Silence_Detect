"""오디오 분석기 데이터 모델 정의."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np


@dataclass
class AnalysisConfig:
    """UI에서 사용자가 설정하는 분석 파라미터 집합."""

    frame_ms: int = 20                  # 프레임 길이 (ms)
    hop_ms: int = 10                    # 홉 길이 (ms)
    noise_floor_percentile: float = 15  # Noise_Floor 백분위수 (%)
    energy_margin_db: float = 10.0      # Energy_Margin (dB)
    vad_aggressiveness: int = 2         # webrtcvad aggressiveness (0~3)
    zcr_threshold: float = 0.1          # ZCR 임계값
    min_silence_ms: int = 200           # 최소 묵음 지속 시간 (ms)
    silence_merge_ms: int = 50          # 묵음 병합 간격 (ms)


@dataclass
class AnalysisMessage:
    """분석 중 발생한 로그 메시지."""

    level: str      # "info" | "warn" | "error"
    message: str    # 메시지 내용
    timestamp: str  # ISO 8601 형식 (예: "2024-01-01T12:00:00.000Z")


@dataclass
class AudioData:
    """로드된 오디오 신호와 메타데이터."""

    samples: np.ndarray     # float32, shape: (n_samples,) 또는 (n_samples, n_channels)
    sample_rate: int        # 샘플레이트 (Hz)
    n_channels: int         # 채널 수
    duration_sec: float     # 길이 (초)
    file_path: str          # 원본 파일 경로


@dataclass
class Frame:
    """분석 단위 오디오 구간."""

    index: int                          # 프레임 인덱스
    start_ms: float                     # 시작 시간 (ms)
    end_ms: float                       # 종료 시간 (ms)
    samples: np.ndarray                 # 해당 구간 샘플
    log_energy: float | None = None
    zcr: float | None = None
    vad_speech: bool | None = None      # webrtcvad 결과 (True=음성)
    energy_silence: bool | None = None  # 에너지 기반 묵음 판별 결과
    final_silence: bool | None = None   # 앙상블 최종 묵음 판별 결과


@dataclass
class SilenceSegment:
    """묵음 구간 정보."""

    start_ms: float     # 시작 시간 (ms)
    end_ms: float       # 종료 시간 (ms)
    duration_ms: float  # 지속 시간 (ms)


@dataclass
class DelayResult:
    """지연 보정 계산 결과."""

    coarse_delay_ms: float      # Cross-correlation으로 추정한 coarse 지연량 (ms)
    refined_delay_ms: float     # DTW로 세부 보정한 지연량 (ms)
    applied_delay_ms: float     # 실제 적용된 최종 지연량 (ms)
    dtw_used: bool              # DTW 세부 보정 적용 여부


@dataclass
class SilenceMetrics:
    """묵음 관련 지표 (수치만 포함, 구간 목록은 AnalysisResult에서 관리)."""

    silence_leakage: float      # ref 묵음 중 dif에 소리가 있는 비율 (0~1)
    false_silence: float        # ref Non-Silence 중 dif가 묵음인 비율 (0~1)
    dif_silence_count: int      # dif 묵음 구간 총 개수
    dif_total_silence_ms: float # dif 묵음 총 시간 (ms)


@dataclass
class SpectrogramData:
    """스펙트로그램 데이터."""

    magnitude_db: np.ndarray    # shape: (n_freq, n_time), dB 스케일
    frequencies: np.ndarray     # 주파수 축 (Hz)
    times: np.ndarray           # 시간 축 (s)


@dataclass
class SpectrumData:
    """스펙트럼 분석 결과."""

    ref_centroid: np.ndarray        # ref Spectral Centroid 시계열 (Hz)
    dif_centroid: np.ndarray        # dif Spectral Centroid 시계열 (Hz)
    ref_rolloff: np.ndarray         # ref Spectral Rolloff 시계열 (Hz)
    dif_rolloff: np.ndarray         # dif Spectral Rolloff 시계열 (Hz)
    ref_pitch: np.ndarray           # ref 피치 시계열 (Hz, NaN=미검출)
    dif_pitch: np.ndarray           # dif 피치 시계열 (Hz, NaN=미검출)
    mean_pitch_diff_hz: float       # 유효 프레임 기준 평균 피치 차이 (Hz)
    ref_zcr: np.ndarray             # ref ZCR 시계열
    dif_zcr: np.ndarray             # dif ZCR 시계열
    ref_spectrogram: SpectrogramData
    dif_spectrogram: SpectrogramData


@dataclass
class MetricStatus:
    """지표 계산 상태."""

    value: Optional[float]          # 계산된 값 (실패 시 None)
    status: str                     # "success" | "N/A" | "failed"
    reason: Optional[str] = None    # 실패 사유 (optional)


@dataclass
class AnalysisResult:
    """전체 분석 결과."""

    # 입력 정보
    ref_path: str
    dif_path: str
    analysis_timestamp: str     # ISO 8601
    config: AnalysisConfig

    # 신호 데이터 (시각화용)
    ref_audio: AudioData
    dif_audio: AudioData        # 포맷 정규화 후
    dif_aligned: np.ndarray     # 지연 보정 후 정렬된 dif 샘플

    # 지연 보정
    delay: DelayResult

    # 묵음 구간
    ref_silence_segments: list[SilenceSegment]
    dif_silence_segments: list[SilenceSegment]
    false_silence_segments: list[SilenceSegment]
    silence_leakage_segments: list[SilenceSegment]
    silence_metrics: SilenceMetrics

    # 음질 지표
    snr_db: MetricStatus
    pesq_score: MetricStatus
    stoi_score: MetricStatus
    rms_diff_db: MetricStatus
    clipping_ratio: MetricStatus
    ref_noise_floor_db: MetricStatus
    dif_noise_floor_db: MetricStatus

    # 스펙트럼 분석
    spectrum: Optional[SpectrumData]

    # 오류 로그
    error_log: list[AnalysisMessage] = field(default_factory=list)
